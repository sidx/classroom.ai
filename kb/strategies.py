from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
import copy
from config.logging import logger
from kb.factory import KnowledgeBaseFactory
from kb.serializers import ProviderContext
from utils.common import UserData
from kb.dao import KnowledgeBaseDao, IngestionRunDao
from kb.models import KBState, Integration, IntegrationType
from utils.connection_handler import ConnectionHandler
from utils.kafka.constants import KAFKA_SERVICE_CONFIG_MAPPING, KafkaServices, ETL_EXTERNAL_DATA
from utils.kafka.kafka_utils import almanac_partitioner
from utils.serializers import ResponseData


# from knowledge_base.locksmith_calls import _call_grant_data_source_access

class ProviderStrategy(ABC):
    """Base strategy interface for handling different provider types"""

    @abstractmethod
    async def start_loading(
            self,
            provider_context: ProviderContext,
            team_id: Optional[str],
            connection_handler: ConnectionHandler,
            user_data: UserData,
            integration: Integration
    ) -> ResponseData:
        """Start loading data from the provider"""
        pass

class ProviderStrategyFactory:
    """Factory for creating provider strategies"""

    @staticmethod
    def get_strategy(
            provider_type: str,
            knowledge_base_dao: KnowledgeBaseDao,
            ingestion_run_dao: IngestionRunDao
    ) -> ProviderStrategy:
        """Get the appropriate strategy for the provider type"""
        if provider_type == "azure_devops" or provider_type == "github" or provider_type == "gitlab":
            return AzureDevOpsStrategy(knowledge_base_dao, ingestion_run_dao)
        elif provider_type == IntegrationType.google_docs.value:
            return GoogleDocsStrategy(knowledge_base_dao, ingestion_run_dao)
        elif provider_type == "quip":
            return QuipStrategy(knowledge_base_dao, ingestion_run_dao)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")


class AzureDevOpsStrategy(ProviderStrategy):
    """Strategy for handling Azure DevOps repositories"""

    def __init__(self, knowledge_base_dao: KnowledgeBaseDao, ingestion_run_dao: IngestionRunDao):
        self.knowledge_base_dao = knowledge_base_dao
        self.ingestion_run_dao = ingestion_run_dao

    async def start_loading(
            self,
            provider_context: ProviderContext,
            team_id: Optional[str],
            connection_handler: ConnectionHandler,
            user_data: UserData,
            integration: Integration
    ) -> ResponseData:
        try:
            kb = None

            if not provider_context.kb_id:
                extractor = KnowledgeBaseFactory.get_extractor(
                    provider_context.provider.value,
                    repo_url=provider_context.credentials["url"],
                    branch_name=provider_context.credentials["branch_name"],
                    pat=provider_context.credentials.get("pat")
                )

                # First check if project is public
                is_public = await extractor.is_project_public()
                validation_result = {}
                # Validate credentials
                if not is_public:
                    validation_result = await extractor.validate_credentials()
                    if not validation_result["is_valid"]:
                        return ResponseData.model_construct(
                            success=False,
                            message=validation_result["message"]
                        )
                # Check for existing knowledge base with same source identifier and user
                existing_kb = await self.knowledge_base_dao.get_by_source_and_user(
                    source_identifier=provider_context.credentials["url"],
                    user_id=user_data.userId if user_data else None,
                    org_id=user_data.orgId if user_data else None
                )

                if existing_kb:
                    logger.info(f"User already has a knowledge base for this source: {existing_kb.id}")
                    return ResponseData.model_construct(
                        success=False,
                        message="You already have a knowledge base for this repository",
                        data={"existing_kb_id": existing_kb.id}
                    )
                # Create settings_json with provider and credentials
                settings_json = {
                    "provider": provider_context.provider.value,
                    "credentials": copy.deepcopy(provider_context.credentials),
                    # Store user info for system operations like cron jobs
                    "user_id": user_data.userId if user_data else None,
                    "org_id": user_data.orgId if user_data else None
                }

                kb = await self.knowledge_base_dao.create_knowledge_base(
                    integration_id=integration.id,
                    name=provider_context.kb_name,
                    source_identifier=provider_context.credentials["url"],
                    kb_type="repo",
                    state=KBState.indexing,
                    team_id=team_id if team_id else None,
                    last_indexed_at=datetime.now(timezone.utc),
                    created_by=user_data.userId if user_data else None,
                    settings_json=settings_json,  # Add the settings_json here
                    org_id=user_data.orgId if user_data else None,
                    is_updatable=provider_context.is_updatable if provider_context.is_updatable else False
                )

                # if team_id:
                #     await _call_grant_data_source_access(team_id, knowledge_base_id=kb.id, user_data=None)
                # await _call_grant_data_source_access(knowledge_base_id=kb.id, user_id=user_data.userId, user_data=None, org_id=None, team_id=None)
            else:
                kb = await self.knowledge_base_dao.get_by_id(int(provider_context.kb_id))

                if not kb:
                    raise ValueError(f"Knowledge base with id {provider_context.kb_id} does not exist.")

                extractor = KnowledgeBaseFactory.get_extractor(
                    provider_context.provider.value,
                    repo_url=kb.settings_json["credentials"]["url"],
                    branch_name=kb.settings_json["credentials"]["branch_name"],
                    pat=kb.settings_json["credentials"].get("pat")
                )

                # First check if project is public
                is_public = await extractor.is_project_public()
                validation_result = {}
                # Validate credentials
                if not is_public:
                    validation_result = await extractor.validate_credentials()
                    if not validation_result["is_valid"]:
                        if not validation_result["token_valid"]:
                            await self.knowledge_base_dao.update_state_by_id(kb.id, KBState.token_error)
                        return ResponseData.model_construct(
                            success=False,
                            message=validation_result["message"]
                        )

                await self.knowledge_base_dao.update_state_by_id(kb.id, KBState.updating)

            ingestion_run = await self.ingestion_run_dao.create_ingestion_run(
                kb_id=kb.id,
                status="running"
            )
            logger.info(f"[Azure DevOps] IngestionRun created with ID: {ingestion_run.id}")

            event = {
                "payload": {
                    "provider": str(provider_context.provider.value),
                    "knowledge_base_id": kb.id,
                    "pat": provider_context.credentials.get("pat") if provider_context.credentials else kb.settings_json.get("credentials", {}).get("pat"),
                    "url": provider_context.credentials.get("url") if provider_context.credentials else kb.settings_json.get("credentials", {}).get("url"),
                    "branch_name": provider_context.credentials.get("branch_name") if provider_context.credentials else kb.settings_json.get("credentials", {}).get("branch_name"),
                    "ingestion_run_id": ingestion_run.id,
                    "mode": "UPDATE" if provider_context.kb_id else "ADD"
                }
            }
            logger.info(f"Event to be emitted: {event}")

            await connection_handler.event_emitter.emit(
                topics=KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][ETL_EXTERNAL_DATA]["topics"],
                partition_value=str(almanac_partitioner.partition()),
                event=event
            )

            await connection_handler.session.commit()
            return ResponseData.model_construct(
                success=True,
                data={
                    "kb": {
                        "id": kb.id,
                        "name": kb.name,
                        "source_identifier": kb.source_identifier,
                        "kb_type": kb.kb_type,
                        "state": kb.state.value if kb.state else None
                    },
                    "is_public": is_public,
                    "is_valid_cred": validation_result
                }
            )

        except Exception as e:
            await connection_handler.session.rollback()
            logger.error(f"Failed to start loading Azure DevOps: {str(e)}")
            return ResponseData.model_construct(success=False, message=f"Transaction failed: {str(e)}")


class GoogleDocsStrategy(ProviderStrategy):

    def __init__(self, knowledge_base_dao: KnowledgeBaseDao, ingestion_run_dao: IngestionRunDao):
        self.knowledge_base_dao = knowledge_base_dao
        self.ingestion_run_dao = ingestion_run_dao

    async def start_loading(
            self,
            provider_context: ProviderContext,
            team_id: Optional[str],
            connection_handler: ConnectionHandler,
            user_data: UserData,
            integration: Integration
    ) -> ResponseData:
        try:
            extractor = KnowledgeBaseFactory.get_extractor(
                name=IntegrationType.google_docs.value,
                docs=provider_context.credentials.get("docs", []),
                token=provider_context.credentials.get("token", "")
            )

            validation_result = await extractor.validate_credentials()
            if not validation_result['is_valid']:
                return ResponseData.model_construct(
                    success=False,
                    message=validation_result["message"]
                )

            # Generate a unique source identifier by combining all URLs
            doc_ids = [doc['id'] for doc in provider_context.credentials.get("docs", [])]
            source_identifier = "|".join(sorted(doc_ids))

            if not provider_context.kb_id:
                # Check for existing knowledge base with same source identifier and user
                existing_kb = await self.knowledge_base_dao.get_by_source_and_user(
                    source_identifier=source_identifier,
                    user_id=user_data.userId if user_data else None,
                    org_id=user_data.orgId if user_data else None
                )

                if existing_kb:
                    logger.info(f"User already has a knowledge base for this source: {existing_kb.id}")
                    return ResponseData.model_construct(
                        success=False,
                        message="You already have a knowledge base for this document(s)",
                        data={"existing_kb_id": existing_kb.id}
                    )
                # Create settings_json with provider and credentials
                settings_json = {
                    "provider": provider_context.provider.value,
                    "credentials": provider_context.credentials,
                    # Store user info for system operations like cron jobs
                    "user_id": user_data.userId if user_data else None,
                    "org_id": user_data.orgId if user_data else None
                }

                kb = await self.knowledge_base_dao.create_knowledge_base(
                    integration_id=integration.id,
                    name=provider_context.kb_name,
                    source_identifier=source_identifier,
                    kb_type="google_docs",
                    state=KBState.indexing,
                    team_id=team_id if team_id else None,
                    last_indexed_at=datetime.now(timezone.utc),
                    created_by=user_data.userId if user_data else None,
                    settings_json=settings_json,  # Add the settings_json here
                    org_id=user_data.orgId if user_data else None
                )
                # if team_id:
                #     await _call_grant_data_source_access(team_id, knowledge_base_id=kb.id, user_data=None)
                # await _call_grant_data_source_access(knowledge_base_id=kb.id, user_id=user_data.userId, user_data=None,
                #                                      org_id=None, team_id=None)
            else:
                kb = await self.knowledge_base_dao.get_by_id(int(provider_context.kb_id))

                if not kb:
                    raise ValueError(f"Knowledge base with id {provider_context.kb_id} does not exist.")

                # Update credentials and state together
                await self.knowledge_base_dao.update_kb_credentials(
                    kb_id=kb.id,
                    new_credentials=provider_context.credentials,
                    user_data={"userId": user_data.userId, "orgId": user_data.orgId} if user_data else None,
                    new_state=KBState.indexing,
                    commit=False
                )
                logger.info(f"Updated credentials and state for knowledge base {kb.id}")

            ingestion_run = await self.ingestion_run_dao.create_ingestion_run(
                kb_id=kb.id,
                status="running"
            )
            logger.info(f"[Google Docs] IngestionRun created with ID: {ingestion_run.id}")

            event = {
                "payload": {
                    "provider": str(provider_context.provider.value),
                    "knowledge_base_id": kb.id,
                    "token": provider_context.credentials.get("token"),
                    "docs": provider_context.credentials.get("docs", []),
                    "ingestion_run_id": ingestion_run.id,
                    "mode": "UPDATE" if provider_context.kb_id else "ADD"
                }
            }
            logger.info(f"Event to be emitted: {event}")

            await connection_handler.event_emitter.emit(
                topics=KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][ETL_EXTERNAL_DATA]["topics"],
                partition_value=str(almanac_partitioner.partition()),
                event=event
            )

            await connection_handler.session.commit()
            return ResponseData.model_construct(
                success=True,
                data={
                    "kb": {
                        "id": kb.id,
                        "name": kb.name,
                        "source_identifier": kb.source_identifier,
                        "kb_type": kb.kb_type,
                        "state": kb.state.value if kb.state else None
                    },
                    "is_valid_cred": validation_result
                }
            )

        except Exception as e:
            await connection_handler.session.rollback()
            logger.error(f"Failed to start loading Google Docs: {str(e)}")
            return ResponseData.model_construct(success=False, message=f"Transaction failed: {str(e)}")


class QuipStrategy(ProviderStrategy):
    """Strategy for handling Quip documents"""

    def __init__(self, knowledge_base_dao: KnowledgeBaseDao, ingestion_run_dao: IngestionRunDao):
        self.knowledge_base_dao = knowledge_base_dao
        self.ingestion_run_dao = ingestion_run_dao

    async def start_loading(
            self,
            provider_context: ProviderContext,
            team_id: Optional[str],
            connection_handler: ConnectionHandler,
            user_data: UserData,
            integration: Integration
    ) -> ResponseData:
        try:
            kb = None

            if not provider_context.kb_id:
                # Create a Quip extractor with the provided credentials
                extractor = KnowledgeBaseFactory.get_extractor(
                    provider_context.provider.value,
                    pat=provider_context.credentials.get("pat"),
                    urls=provider_context.credentials.get("urls", [])
                )

                # Validate credentials
                validation_result = await extractor.validate_credentials()
                if not validation_result["is_valid"]:
                    return ResponseData.model_construct(
                        success=False,
                        message=validation_result["message"]
                    )

                # Generate a unique source identifier by combining all URLs
                source_identifier = "|".join(sorted(provider_context.credentials.get("urls", [])))
                # Check for existing knowledge base with same source identifier and user
                existing_kb = await self.knowledge_base_dao.get_by_source_and_user(
                    source_identifier=source_identifier,
                    user_id=user_data.userId if user_data else None,
                    org_id=user_data.orgId if user_data else None
                )

                if existing_kb:
                    logger.info(f"User already has a knowledge base for this source: {existing_kb.id}")
                    return ResponseData.model_construct(
                        success=False,
                        message="You already have a knowledge base for these Quip documents",
                        data={"existing_kb_id": existing_kb.id}
                    )

                # Create settings_json with provider and credentials
                settings_json = {
                    "provider": provider_context.provider.value,
                    "credentials": copy.deepcopy(provider_context.credentials),
                    # Store user info for system operations like cron jobs
                    "user_id": user_data.userId if user_data else None,
                    "org_id": user_data.orgId if user_data else None
                }

                kb = await self.knowledge_base_dao.create_knowledge_base(
                    integration_id=integration.id,
                    name=provider_context.kb_name,
                    source_identifier=source_identifier,
                    kb_type="quip",
                    state=KBState.indexing,
                    team_id=team_id if team_id else None,
                    last_indexed_at=datetime.now(timezone.utc),
                    created_by=user_data.userId if user_data else None,
                    settings_json=settings_json,
                    org_id=user_data.orgId if user_data else None,
                    is_updatable=provider_context.is_updatable if provider_context.is_updatable else False
                )

                # if team_id:
                #     await _call_grant_data_source_access(team_id, knowledge_base_id=kb.id, user_data=None)
                # await _call_grant_data_source_access(knowledge_base_id=kb.id, user_id=user_data.userId, user_data=None, org_id=None, team_id=None)
            else:
                kb = await self.knowledge_base_dao.get_by_id(int(provider_context.kb_id))

                if not kb:
                    raise ValueError(f"Knowledge base with id {provider_context.kb_id} does not exist.")

                extractor = KnowledgeBaseFactory.get_extractor(
                    provider_context.provider.value,
                    pat=kb.settings_json["credentials"]["pat"],
                    urls=kb.settings_json["credentials"]["urls"]
                )

                # Validate credentials
                validation_result = await extractor.validate_credentials()
                if not validation_result["is_valid"]:

                    await self.knowledge_base_dao.update_state_by_id(kb.id, KBState.token_error)
                    return ResponseData.model_construct(
                        success=False,
                        message=validation_result["message"]
                    )

                await self.knowledge_base_dao.update_state_by_id(kb.id, KBState.updating)

            ingestion_run = await self.ingestion_run_dao.create_ingestion_run(
                kb_id=kb.id,
                status="running"
            )
            logger.info(f"[Quip] IngestionRun created with ID: {ingestion_run.id}")

            event = {
                "payload": {
                    "provider": str(provider_context.provider.value),
                    "knowledge_base_id": kb.id,
                    "pat": provider_context.credentials.get("pat") if provider_context.credentials else kb.settings_json.get("credentials", {}).get("pat"),
                    "urls": provider_context.credentials.get("urls", []) if provider_context.credentials else kb.settings_json.get("credentials", {}).get("urls", []),
                    "ingestion_run_id": ingestion_run.id,
                    "mode": "UPDATE" if provider_context.kb_id else "ADD"
                }
            }
            logger.info(f"Event to be emitted: {event}")

            await connection_handler.event_emitter.emit(
                topics=KAFKA_SERVICE_CONFIG_MAPPING[KafkaServices.almanac][ETL_EXTERNAL_DATA]["topics"],
                partition_value=str(almanac_partitioner.partition()),
                event=event
            )

            await connection_handler.session.commit()
            return ResponseData.model_construct(
                success=True,
                data={
                    "kb": {
                        "id": kb.id,
                        "name": kb.name,
                        "source_identifier": kb.source_identifier,
                        "kb_type": kb.kb_type,
                        "state": kb.state.value if kb.state else None
                    },
                    "is_valid_cred": validation_result
                }
            )

        except Exception as e:
            await connection_handler.session.rollback()
            logger.error(f"Failed to start loading Quip: {str(e)}")
            return ResponseData.model_construct(success=False, message=f"Transaction failed: {str(e)}")
