from typing import Optional, List
import copy
from indexing.db import ElasticSearchVectorDb
from indexing.serializers import FileContent, SourceItemKind
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from config.logging import logger
from config.settings import loaded_config
from kb.dao import IntegrationDao, KnowledgeBaseDao, IngestionRunDao
from kb.factory import KnowledgeBaseFactory
from kb.models import KBState
from kb.serializers import KnowledgeBaseRequest, GetVectorSearchRequest, LocalFileContext, ProviderContext, \
    GetKBStatusRequest, ShareKnowledgeBaseRequest, GetKbRequest, UpdateKB
# from clerk_integration.utils import UserData
import hashlib
import uuid
from kb.strategies import ProviderStrategyFactory
from utils.connection_handler import ConnectionHandler
from utils.exceptions import ApiException, CustomException
from utils.kafka.constants import KAFKA_SERVICE_CONFIG_MAPPING, KafkaServices, ETL_EXTERNAL_DATA
from utils.kafka.kafka_utils import almanac_partitioner
from utils.serializers import ResponseData
# from knowledge_base.locksmith_calls import (
#     _call_grant_data_source_access,
#     _call_revoke_data_source_access,
#     _call_check_data_source_access,
#     _call_get_accessible_datasources_by_user,
#     _call_get_org_accessible_datasources,
#     _call_get_team_accessible_datasources,
#     _call_get_datasource_access_details,
#     _call_revoke_specific_data_source_access
# )
from utils.common import UserData

class KnowledgeBaseService:
    def __init__(self, session: AsyncSession):
        self.integration_dao = IntegrationDao(session)
        self.knowledge_base_dao = KnowledgeBaseDao(session)
        self.ingestion_run_dao = IngestionRunDao(session)
        self.vector_db = ElasticSearchVectorDb()
        self.vector_db.elastic_search_url = [loaded_config.elastic_search_url]

    async def start_loading(
            self,
            request: KnowledgeBaseRequest,
            connection_handler: ConnectionHandler,
            user_data: UserData
    ) -> ResponseData:
        logger.info("start_loading method invoked")

        if request.context == "add_context_through_provider":
            return await self._handle_provider_context(
                request.add_context_through_provider,
                request.team_id,
                connection_handler,
                user_data
            )

        elif request.context == "add_context_through_local_files":
            return await self._handle_local_file_context(request.add_context_through_local_files, user_data, connection_handler, request.team_id)

        else:
            logger.error(f"Unsupported context type: {request.context}")
            return ResponseData.model_construct(success=False, message=f"Unsupported context: {request.context}")

    async def _handle_provider_context(
            self,
            provider_context: ProviderContext,
            team_id: Optional[str],
            connection_handler: ConnectionHandler,
            user_data: UserData
    ) -> ResponseData:
        if not provider_context:
            logger.error("Provider context data missing")
            return ResponseData.model_construct(success=False, message="Provider context missing")

        integration = await self.integration_dao.get_by_type(provider_context.provider)
        if not integration:
            logger.error(f"Integration not found for type: {provider_context.provider} and org_id: {user_data.orgId}")
            return ResponseData.model_construct(success=False, message="Integration not found")

        if not provider_context.kb_id:
            expected_fields = integration.credentials_json or {}
            missing_fields = [
                key for key in expected_fields.keys()
                if not provider_context.credentials or key not in provider_context.credentials
            ]
            if missing_fields:
                logger.error(f"Missing credential fields: {missing_fields}")
                return ResponseData.model_construct(success=False, message=f"Missing credential fields: {missing_fields}")

        try:
            # Get the appropriate strategy for the provider type
            strategy = ProviderStrategyFactory.get_strategy(
                provider_context.provider.value,
                self.knowledge_base_dao,
                self.ingestion_run_dao
            )

            # Use the strategy to handle the provider
            return await strategy.start_loading(
                provider_context,
                team_id,
                connection_handler,
                user_data,
                integration
            )
        except ValueError as e:
            logger.error(f"Unsupported provider: {provider_context.provider}")


    async def _handle_local_file_context(self, local_context: LocalFileContext, user_data: UserData, connection_handler: ConnectionHandler, team_id) -> ResponseData:
        try:
            if not local_context:
                logger.error("Local file context missing")
                return ResponseData.model_construct(success=False, message="Local file context missing")

            logger.info(f"Received local file context: {local_context}")
            # Right now no action for local files
            if not local_context:
                logger.error("Local context data missing")
                return ResponseData.model_construct(success=False, message="Provider context missing")

            integration = await self.integration_dao.get_by_type(local_context.provider)
            if not integration:
                logger.error(f"Integration not found for type: {local_context.provider} and org_id: {user_data.orgId}")
                return ResponseData.model_construct(success=False, message="Integration not found")

            kb = None

            if not local_context.kb_id:

                # Check for existing knowledge base with same source identifier and user
                existing_kb = await self.knowledge_base_dao.get_by_source_and_user(
                    source_identifier=local_context.path,
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
                    "provider": local_context.provider.value,
                    "credentials": {},
                    # Store user info for system operations like cron jobs
                    "user_id": user_data.userId if user_data else None,
                    "org_id": user_data.orgId if user_data else None
                }

                kb = await self.knowledge_base_dao.create_knowledge_base(
                    integration_id=integration.id,
                    name=local_context.kb_name,
                    source_identifier=local_context.path,
                    kb_type="file",
                    state=KBState.indexing,
                    team_id=None,
                    last_indexed_at=datetime.now(timezone.utc),
                    created_by=user_data.userId if user_data else None,
                    settings_json=settings_json,  # Add the settings_json here
                    org_id=user_data.orgId if user_data else None,
                    is_updatable=False

                )

                # if team_id:
                #     await _call_grant_data_source_access(team_id, knowledge_base_id=kb.id, user_data=None)
                # await _call_grant_data_source_access(knowledge_base_id=kb.id, user_id=user_data.userId, user_data=None,
                #                                      org_id=None, team_id=None)
            else:
                kb = await self.knowledge_base_dao.get_by_id(int(local_context.kb_id))

                if not kb:
                    raise ValueError(f"Knowledge base with id {local_context.kb_id} does not exist.")

                await self.knowledge_base_dao.update_state_by_id(kb.id, KBState.updating)

            ingestion_run = await self.ingestion_run_dao.create_ingestion_run(
                kb_id=kb.id,
                status="running"
            )
            logger.info(f"[Local File] IngestionRun created with ID: {ingestion_run.id}")

            event = {
                "payload": {
                    "provider": str(local_context.provider.value),
                    "knowledge_base_id": kb.id,
                    "path": local_context.path,
                    "content": local_context.content,
                    "version_tag" : '1.0',
                    "provider_item_id" : 'local',
                    "checksum" : hashlib.sha256(local_context.content.encode()).hexdigest(),
                    "uuid_str" : str(uuid.uuid4()),
                    "kind" : SourceItemKind.file.value,
                    "ingestion_run_id": ingestion_run.id,
                    "mode": "UPDATE" if local_context.kb_id else "ADD"
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
                    }
                }
            )

        except Exception as e:
            await connection_handler.session.rollback()
            logger.error(f"Failed to start loading Local File: {str(e)}")
            return ResponseData.model_construct(success=False, message=f"Transaction failed: {str(e)}")

    # async def get_vector_search(self, request: GetVectorSearchRequest) -> ResponseData:
    #     response_data = ResponseData.model_construct(success=False)
    #     logger.info(f"get_vector_search method invoked")
    #
    #     try:
    #         for i in request.knowledge_base_id:
    #             has_access = await _call_check_data_source_access(i, request.user_id, request.org_id, request.team_id)
    #             if not has_access:
    #                 return ResponseData.model_construct(success=False, message="User does not have access to this knowledge base")
    #
    #         await self.vector_db.connect()
    #
    #         # Call search_and_fetch_content with the correct index name and data source string
    #         result = await self.vector_db.search_and_fetch_content(
    #             request=request,
    #             index_name="knowledge_base_index"
    #         )
    #
    #         response_data.success = True
    #         response_data.data = result
    #         logger.info(f"get_vector_search method fetched")
    #         return response_data
    #
    #     except Exception as e:
    #         logger.error(f"Search failed for request: {request.dict()}. Error: {str(e)}")
    #         raise ApiException(f"Search operation failed: {str(e)}")
    #
    #     finally:
    #         await self.vector_db.close()

    async def get_integrations(self) -> ResponseData:
        logger.info(f"get_integrations method invoked")
        return ResponseData.model_construct(success=True, data=await self.integration_dao.get_all_integrations())

    # async def get_indexing_status(self, user_data: UserData, request: GetKBStatusRequest) -> ResponseData:
    #     try:
    #         logger.info("Fetching indexing status")
    #         data = {}
    #
    #         # Step 1: If team_id is provided, filter only KBs belonging to that team
    #         if request.team_id:
    #             team_kbs = await _call_get_team_accessible_datasources(request.team_id)
    #             data = {
    #                 "personal": [],
    #                 "team": team_kbs,
    #                 "organization": []
    #             }
    #
    #         else:
    #             data = await _call_get_accessible_datasources_by_user(user_data)
    #             # org_kb_ids = data.get("organization", [])
    #             # data["personal"] = [kb_id for kb_id in data.get("personal", []) if kb_id in org_kb_ids]
    #
    #         # Step 2: If kb_ids are provided, filter all categories
    #         if request.kb_ids:
    #             for category in data:
    #                 data[category] = [kb_id for kb_id in data[category] if kb_id in request.kb_ids]
    #
    #         # Step 3: Get indexing status
    #         status_list = await self.knowledge_base_dao.get_indexing_status(data, user_data.userId, user_data.orgId)
    #
    #         return ResponseData.model_construct(
    #             success=True,
    #             data={"knowledge_bases": status_list}
    #         )
    #
    #     except Exception as e:
    #         logger.error(f"Failed to fetch indexing status: {str(e)}")
    #         return ResponseData.model_construct(
    #             success=False,
    #             message=f"Failed to fetch indexing status: {str(e)}"
    #         )
    #
    # async def delete_knowledge_bases(self, kb_ids: List[int], connection_handler: ConnectionHandler, user_data: UserData) -> ResponseData:
    #     """
    #     Delete knowledge bases and their associated documents from both Elasticsearch and database.
    #
    #     Args:
    #         kb_ids: List of knowledge base IDs to delete
    #         connection_handler: Database connection handler for transaction management
    #
    #     Returns:
    #         ResponseData with success/failure status and message
    #     """
    #     try:
    #         logger.info("Starting deletion of knowledge bases", extra={"kb_ids": kb_ids})
    #
    #         for kb_id in kb_ids:
    #             kb = await self.knowledge_base_dao.get_by_id(kb_id)
    #
    #             if kb.created_by != user_data.userId:
    #                 logger.error("User does not have permission to delete this knowledge base", extra={
    #                     "kb_id": kb_id,
    #                     "user_id": user_data.userId,
    #                     "created_by": kb.created_by
    #                 })
    #                 raise CustomException(f"Do not have access to delete knowledge base: {kb.name}")
    #
    #         # Delete from Elasticsearch first
    #         await self.vector_db.connect()
    #         try:
    #
    #             for kb_id in kb_ids:
    #                 await _call_revoke_data_source_access(kb_id)
    #
    #                 logger.debug("Deleting documents from Elasticsearch", extra={
    #                     "kb_id": kb_id,
    #                     "index": "knowledge_base_index"
    #                 })
    #                 result = await self.vector_db.delete_documents_by_kb_id(
    #                     index_name="knowledge_base_index",
    #                     kb_id=kb_id,
    #                     id_field="knowledge_base_id"
    #                 )
    #                 logger.info("Successfully deleted documents from Elasticsearch", extra={
    #                     "kb_id": kb_id,
    #                     "deleted_count": result["deleted"],
    #                     "failed_count": result["failed"]
    #                 })
    #         except Exception as e:
    #             logger.error("Failed to delete documents from Elasticsearch", extra={
    #                 "kb_ids": kb_ids,
    #                 "error": str(e)
    #             })
    #             raise
    #         finally:
    #             await self.vector_db.close()
    #
    #
    #         logger.debug("Deleting knowledge bases from database", extra={"kb_ids": kb_ids})
    #         await self.knowledge_base_dao.delete_knowledge_bases(kb_ids)
    #
    #         await connection_handler.session.commit()
    #
    #         logger.info("Successfully completed knowledge base deletion", extra={"kb_ids": kb_ids})
    #         return ResponseData.model_construct(
    #             success=True,
    #             data={
    #                 "message": f"Successfully deleted {len(kb_ids)} knowledge bases and their associated data",
    #                 "deleted_kb_ids": kb_ids
    #             }
    #         )
    #
    #     except Exception as e:
    #         await connection_handler.session.rollback()
    #         logger.error("Failed to delete knowledge bases", extra={
    #             "kb_ids": kb_ids,
    #             "error": str(e),
    #             "error_type": type(e).__name__
    #         })
    #         raise CustomException(e.__str__())
    #
    # async def share_knowledge_bases(self, request: ShareKnowledgeBaseRequest, user_data: UserData) -> ResponseData:
    #     try:
    #         logger.info("Sharing knowledge bases", extra={"kb_ids": request.kb_ids, "team_id": request.team_id})
    #
    #         for kb_id in request.kb_ids:
    #             kb = await self.knowledge_base_dao.get_by_id(kb_id)
    #
    #             if kb.created_by != user_data.userId:
    #                 logger.error("User does not have permission to share this knowledge base", extra={
    #                     "kb_id": kb_id,
    #                     "user_id": user_data.userId,
    #                     "created_by": kb.created_by
    #                 })
    #                 raise CustomException(f"Do not have access to share knowledge base: {kb.name}")
    #
    #         for kb_id in request.kb_ids:
    #             access = await _call_get_datasource_access_details(kb_id)
    #             current = {
    #                 "users": access.get("users", []),
    #                 "teams": access.get("teams", []),
    #                 "orgs": access.get("organizations", [])
    #             }
    #
    #             requested = {
    #                 "users": request.user_id or [],
    #                 "teams": request.team_id or [],
    #                 "orgs": request.org_id or []
    #             }
    #
    #             to_revoke = {
    #                 "users": [uid for uid in current["users"] if uid not in requested["users"]],
    #                 "teams": [tid for tid in current["teams"] if tid not in requested["teams"]],
    #                 "orgs": [oid for oid in current["orgs"] if oid not in requested["orgs"]],
    #             }
    #
    #             to_grant = {
    #                 "users": [uid for uid in requested["users"] if uid not in current["users"]],
    #                 "teams": [tid for tid in requested["teams"] if tid not in current["teams"]],
    #                 "orgs": [oid for oid in requested["orgs"] if oid not in current["orgs"]],
    #             }
    #
    #             logger.info(f"Access changes for KB {kb_id}", extra={
    #                 "current": current,
    #                 "to_revoke": to_revoke,
    #                 "to_grant": to_grant
    #             })
    #
    #             # Revoke access
    #             for user_id in to_revoke["users"]:
    #                 if user_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, user_id=user_id)
    #                     logger.info("Revoked access for user", extra={"kb_id": kb_id, "user_id": user_id})
    #
    #             for team_id in to_revoke["teams"]:
    #                 if team_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, team_id=team_id)
    #                     logger.info("Revoked access for team", extra={"kb_id": kb_id, "team_id": team_id})
    #
    #             for org_id in to_revoke["orgs"]:
    #                 if org_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, org_id=org_id)
    #                     logger.info("Revoked access for organization", extra={"kb_id": kb_id, "org_id": org_id})
    #
    #             # Grant access
    #             for user_id in to_grant["users"]:
    #                 if user_id:
    #                     await _call_grant_data_source_access(
    #                         team_id=None,
    #                         knowledge_base_id=kb_id,
    #                         user_data=None,
    #                         user_id=user_id,
    #                         org_id=None
    #                     )
    #                     logger.info("Granted access to user", extra={"kb_id": kb_id, "user_id": user_id})
    #
    #             for team_id in to_grant["teams"]:
    #                 if team_id:
    #                     await _call_grant_data_source_access(
    #                         team_id=team_id,
    #                         knowledge_base_id=kb_id,
    #                         user_data=None,
    #                         user_id=None,
    #                         org_id=None
    #                     )
    #                     logger.info("Granted access to team", extra={"kb_id": kb_id, "team_id": team_id})
    #
    #             for org_id in to_grant["orgs"]:
    #                 if org_id:
    #                     await _call_grant_data_source_access(
    #                         team_id=None,
    #                         knowledge_base_id=kb_id,
    #                         user_data=None,
    #                         user_id=None,
    #                         org_id=org_id
    #                     )
    #                     logger.info("Granted access to organization", extra={"kb_id": kb_id, "org_id": org_id})
    #
    #         return ResponseData.model_construct(
    #             success=True,
    #             data={"message": f"Successfully updated sharing for knowledge base"}
    #         )
    #
    #     except Exception as e:
    #         # logger.error("Failed to share knowledge base", exc_info=True)
    #         raise CustomException(e.__str__())
    #
    # async def get_knowledge_bases(self, filter: GetKbRequest, user_data: UserData) -> ResponseData:
    #     try:
    #         data = await _call_get_accessible_datasources_by_user(user_data)
    #         kb_ids = {
    #             "personal_kb_ids": data.get("personal", []),
    #             "team_kb_ids": data.get("team", []),
    #             "org_kb_ids": data.get("organization", [])
    #         }
    #
    #         if filter.team_ids:
    #             for team_id in filter.team_ids:
    #                 team_kbs = await _call_get_team_accessible_datasources(team_id)
    #                 kb_ids["team_kb_ids"].extend(team_kbs)
    #
    #             # Remove duplicates if a KB is accessible by multiple teams
    #             kb_ids["team_kb_ids"] = list(set(kb_ids["team_kb_ids"]))
    #
    #         if filter.org_ids:
    #             for org_id in filter.org_ids:
    #                 org_kbs = await _call_get_org_accessible_datasources(org_id)
    #                 kb_ids["org_kb_ids"].extend(org_kbs)
    #
    #             # Remove duplicates if a KB is accessible by multiple organizations
    #             kb_ids["org_kb_ids"] = list(set(kb_ids["org_kb_ids"]))
    #
    #         # Get knowledge bases with pagination and filtering
    #         result = await self.knowledge_base_dao.get_knowledge_bases_with_pagination(kb_ids, filter)
    #
    #         # Organize knowledge bases by category (personal, team, org)
    #         personal_kbs = []
    #         team_kbs = []
    #         org_kbs = []
    #
    #         for kb in result["knowledge_bases"]:
    #             kb_id = kb["id"]
    #             if kb_id in kb_ids["personal_kb_ids"]:
    #                 personal_kbs.append(kb)
    #             if kb_id in kb_ids["team_kb_ids"]:
    #                 team_kbs.append(kb)
    #             if kb_id in kb_ids["org_kb_ids"]:
    #                 org_kbs.append(kb)
    #
    #         # Structure the response data
    #         knowledge_bases_data = {
    #             "personal": personal_kbs,
    #             "team": team_kbs,
    #             "organization": org_kbs
    #         }
    #
    #         return ResponseData.model_construct(
    #             success=True,
    #             data=knowledge_bases_data,
    #             pagination=result["pagination"]
    #         )
    #
    #     except Exception as e:
    #         logger.error(f"Failed to fetch knowledge bases: {str(e)}")
    #         return ResponseData.model_construct(
    #             success=False,
    #             message=f"Failed to fetch knowledge bases: {str(e)}"
    #         )
    #
    # async def revoke_knowledge_base_access(self, request: ShareKnowledgeBaseRequest, user_data: UserData) -> ResponseData:
    #     try:
    #         for kb_id in request.kb_ids:
    #             for user_id in request.user_id:
    #                 if user_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, user_id=user_id)
    #                     logger.info("Revoked access for user", extra={"kb_id": kb_id, "user_id": user_id})
    #
    #             for team_id in request.team_id:
    #                 if team_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, team_id=team_id)
    #                     logger.info("Revoked access for team", extra={"kb_id": kb_id, "team_id": team_id})
    #
    #             for org_id in request.org_id:
    #                 if org_id:
    #                     await _call_revoke_specific_data_source_access(kb_id, org_id=org_id)
    #                     logger.info("Revoked access for organization", extra={"kb_id": kb_id, "org_id": org_id})
    #
    #             return ResponseData.model_construct(
    #                 success=True,
    #                 data={"message": "Successfully revoked access for knowledge base"}
    #             )
    #     except Exception as e:
    #         raise CustomException(e.__str__())
    #
    # async def is_url_public(self, url: str, provider: str, user_data: UserData) -> ResponseData:
    #     try:
    #         # if url contain `.git` in end remove it
    #         if url.endswith(".git"):
    #             url = url[:-4]
    #         extractor = KnowledgeBaseFactory.get_extractor(provider, repo_url=url)
    #         is_public = await extractor.is_project_public()
    #         return ResponseData.model_construct(
    #             success=True,
    #             data={"is_public": is_public}
    #         )
    #     except Exception as e:
    #         raise CustomException(e.__str__())
    #
    # async def update_knowledge_bases(self, request: UpdateKB, user_data: UserData) -> ResponseData:
    #     try:
    #         kb = await self.knowledge_base_dao.get_by_id(request.kb_id)
    #
    #         if kb.created_by != user_data.userId:
    #             logger.error("User does not have permission to update this knowledge base", extra={
    #                 "kb_id": kb.id,
    #                 "user_id": user_data.userId,
    #                 "created_by": kb.created_by
    #             })
    #             raise CustomException(f"Do not have access to update knowledge base: {kb.name}")
    #
    #         extractor = KnowledgeBaseFactory.get_extractor(
    #             kb.settings_json["provider"],
    #             repo_url=kb.settings_json["credentials"].get("url") if not request.url else request.url,
    #             pat=request.pat if request.pat and request.pat.strip() else kb.settings_json["credentials"].get("pat"),
    #             branch_name=kb.settings_json["credentials"].get("branch_name") if not request.branch_name else request.branch_name
    #         )
    #
    #         is_public = await extractor.is_project_public()
    #         if not is_public:
    #             validation_result = await extractor.validate_credentials()
    #             if not validation_result["is_valid"]:
    #                 raise CustomException(validation_result["message"])
    #
    #         await self.knowledge_base_dao.update_kb_name_and_pat_url_branch(name=request.name if request.name and request.name.strip() else None,
    #                                                              kb_id=kb.id,
    #                                                              pat=request.pat if request.pat and request.pat.strip() else None,
    #                                                              url=request.url if request.url and request.url.strip() else None,
    #                                                              branch_name=request.branch_name if request.branch_name and request.branch_name.strip() else None
    #                                                             )
    #         # name status
    #         return ResponseData.model_construct(
    #             success=True,
    #             data={
    #                 "message": "Successfully updated knowledge base",
    #                 "name": kb.name,
    #                 "status": kb.state.value,
    #                 "update_token": True if kb.state.value == "token_error" else False
    #             }
    #         )
    #     except Exception as e:
    #         raise CustomException(e.__str__())
