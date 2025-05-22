from typing import Optional

from kb.serializers import GetKbRequest
from prometheus.metrics import DB_QUERY_LATENCY
from utils.dao import BaseDao
from kb.models import Integration, IntegrationType, KnowledgeBase, IngestionRun, SourceItem, Chunk, KBState, IngestionError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, func, or_
from utils.decorators import latency
from datetime import datetime
from typing import List


class IntegrationDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=Integration)

    @latency(metric=DB_QUERY_LATENCY)
    async def get_by_type(self, integration_type: IntegrationType) -> Optional[Integration]:
        stmt = (
            select(self.db_model)
            .where(
                self.db_model.type == integration_type,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @latency(metric=DB_QUERY_LATENCY)
    async def get_all_integrations(self) -> List[dict]:
        stmt = select(self.db_model)
        result = await self.session.execute(stmt)
        integrations = result.scalars().all()

        return [
            {
                "id": integration.id,
                "type": integration.type.name,
                "name": integration.name,
                "credentials_json": integration.credentials_json,
                "image_name": integration.image_name,
                "integration_help_url": integration.integration_help_url,
            }
            for integration in integrations
        ]

class KnowledgeBaseDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=KnowledgeBase)

    @latency(metric=DB_QUERY_LATENCY)
    async def create_knowledge_base(self, **kwargs) -> KnowledgeBase:
        kb = KnowledgeBase(**kwargs)
        self.session.add(kb)
        await self.session.flush()
        return kb

    @latency(metric=DB_QUERY_LATENCY)
    async def update_state_by_id(self, kb_id: int, new_state: KBState, commit: bool = True) -> None:
        stmt = (
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(state=new_state)
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()

    @latency(metric=DB_QUERY_LATENCY)
    async def update_kb_credentials(
            self,
            kb_id: int,
            new_credentials: dict,
            user_data: dict = None,
            new_state: KBState = None,
            commit: bool = True
    ) -> None:
        """
        Update credentials inside settings_json and optionally update state

        Args:
            kb_id: Knowledge base ID
            new_credentials: New credentials to store in settings_json
            user_data: Optional user data to update in settings_json
            new_state: Optional new state for the knowledge base
            commit: Whether to commit the transaction
        """
        # First get the current settings_json
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise ValueError(f"Knowledge base with id {kb_id} not found")

        # Create updated settings_json
        updated_settings_json = kb.settings_json.copy() if kb.settings_json else {}
        updated_settings_json["credentials"] = new_credentials

        # Update user info if provided
        if user_data:
            updated_settings_json["user_id"] = user_data.get("userId")
            updated_settings_json["org_id"] = user_data.get("orgId")

        # Prepare update values
        update_values = {"settings_json": updated_settings_json}
        if new_state:
            update_values["state"] = new_state

        # Update the knowledge base
        stmt = (
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(**update_values)
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()

    @latency(metric=DB_QUERY_LATENCY)
    async def get_indexing_status(self, data: dict[str, list[int]], user_id: str, org_id: str = None) -> dict[str, list[dict]]:
        result = {key: [] for key in data.keys()}

        for category, kb_ids in data.items():
            if not kb_ids:
                continue

            # Get knowledge bases with their integration details
            kb_query = (
                select(KnowledgeBase, Integration)
                .join(Integration, KnowledgeBase.integration_id == Integration.id)
                .where(KnowledgeBase.id.in_(kb_ids))
            )
            if org_id is None:
                kb_query = kb_query.where(KnowledgeBase.org_id.is_(None))
            else:
                kb_query = kb_query.where(KnowledgeBase.org_id == org_id)

            kb_result = await self.session.execute(kb_query)

            for kb, integration in kb_result:
                # For each KB, get the latest ingestion run
                latest_run_query = (
                    select(IngestionRun)
                    .where(IngestionRun.kb_id == kb.id)
                    .order_by(IngestionRun.started_at.desc())
                    .limit(1)
                )
                latest_run_result = await self.session.execute(latest_run_query)
                latest_run = latest_run_result.scalar()

                kb_status = {
                    "kb_id": kb.id,
                    "name": kb.name,
                    "state": kb.state.value,
                    "update_token": True if kb.state.value == "token_error" else False,
                    "created_at": kb.created_at,
                    "last_indexed_at": kb.last_indexed_at,
                    "ingestion_status": None,
                    "success_percentage": 0.00,
                    "is_enabled": kb.state != KBState.disabled,
                    "is_creator": kb.created_by == user_id,
                    "is_updatable": kb.is_updatable,
                    "integration": {
                        "id": integration.id,
                        "type": integration.type.name,
                        "name": integration.name,
                        "image_name": integration.image_name,
                        "integration_help_url": integration.integration_help_url
                    }
                }

                if latest_run and latest_run.stats_json:
                    total_chunks = latest_run.stats_json.get("total_chunks", 0)
                    failed_chunks = latest_run.stats_json.get("failed_chunk_elastic_doc_id", [])
                    failed_count = len(failed_chunks) if failed_chunks else 0

                    success_percentage = 0.00
                    if total_chunks > 0:
                        success_percentage = round(100 - (failed_count / total_chunks * 100), 2)

                    kb_status.update({
                        "ingestion_status": latest_run.status,
                        "success_percentage": success_percentage
                    })

                result[category].append(kb_status)

        return result

    async def delete_knowledge_bases(self, kb_ids: List[int]) -> None:
        """
        Delete knowledge bases. Cascading delete will automatically remove related records.
        Transaction handling should be done at service level.
        """
        stmt = delete(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        await self.session.execute(stmt)

    async def get_by_id(self, kb_id: int):
        """Fetch a Knowledge Base by its ID."""
        query = await self.session.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return query.scalar_one_or_none()

    @latency(metric=DB_QUERY_LATENCY)
    async def get_active_knowledge_bases(self) -> List[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.state.not_in([KBState.updating, KBState.disabled, KBState.indexing]))
            .where(KnowledgeBase.is_updatable == True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    @latency(metric=DB_QUERY_LATENCY)
    async def get_kb_ids_by_team(self, kb_ids: List[int], team_id: str) -> List[int]:
        """
        Filter knowledge base IDs to only include those belonging to the specified team.

        Args:
            kb_ids: List of knowledge base IDs to filter
            team_id: Team ID to filter by

        Returns:
            List of knowledge base IDs that belong to the specified team
        """
        if not kb_ids:
            return []

        query = (
            select(KnowledgeBase.id)
            .where(
                KnowledgeBase.id.in_(kb_ids),
                KnowledgeBase.team_id == team_id
            )
        )

        result = await self.session.execute(query)
        matching_ids = result.scalars().all()

        return matching_ids

    @latency(metric=DB_QUERY_LATENCY)
    async def get_by_source_and_user(self, source_identifier: str, user_id: str, org_id: str) -> Optional[KnowledgeBase]:
        """
        Get a knowledge base by source identifier and user ID.

        Args:
            source_identifier: The source identifier (e.g., repository URL)
            user_id: The user ID stored in settings_json
            org_id: The organization ID

        Returns:
            The knowledge base if found, None otherwise
        """
        # We need to use JSON containment operator @> to check if settings_json contains the user_id
        query = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.source_identifier == source_identifier,
                KnowledgeBase.created_by == user_id,
                KnowledgeBase.org_id == org_id
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    @latency(metric=DB_QUERY_LATENCY)
    async def update_memory_key_by_id(self, kb_id: int, key: str, value: dict, commit: bool = False):
        """
        Updates a top-level key in the memory JSONB field with a dict value.
        Overwrites the existing key if it already exists.
        """
        stmt = (
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(memory=KnowledgeBase.memory.op("||")({key: value}))
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)
        if commit:
            await self.session.commit()

    @latency(metric=DB_QUERY_LATENCY)
    async def get_knowledge_bases_with_pagination(
            self,
            kb_ids: dict[str, list[int]],
            filter_params: GetKbRequest
    ) -> dict:
        """
        Get knowledge bases with pagination and filtering.

        Args:
            kb_ids: Dictionary containing KB IDs categorized by access type
            filter_params: Filter parameters from GetKbRequest

        Returns:
            Dictionary with knowledge bases and pagination information
        """
        # Combine all KB IDs into a single list
        all_kb_ids = []
        for category in kb_ids.values():
            all_kb_ids.extend(category)

        # Remove duplicates
        all_kb_ids = list(set(all_kb_ids))

        if not all_kb_ids:
            return {
                "knowledge_bases": [],
                "pagination": {
                    "total_count": 0,
                    "total_pages": 0,
                    "current_page": filter_params.page,
                    "page_size": filter_params.size,
                    "has_next": False,
                    "has_previous": False,
                },
            }

        # Build base query
        base_query = select(KnowledgeBase).where(KnowledgeBase.id.in_(all_kb_ids))

        # Apply state filter if provided
        if filter_params.state:
            base_query = base_query.where(KnowledgeBase.state == filter_params.state)

        # Apply search term filter if provided
        if filter_params.search_term:
            search_term = f"%{filter_params.search_term}%"
            base_query = base_query.where(
                or_(
                    KnowledgeBase.name.ilike(search_term),
                    KnowledgeBase.source_identifier.ilike(search_term)
                )
            )

        # Get total count for pagination
        count_query = select(func.count()).select_from(base_query.subquery())
        total_count_result = await self.session.execute(count_query)
        total_count = total_count_result.scalar()

        # Apply pagination
        page_size = filter_params.size
        page = filter_params.page

        if page_size > 0:
            base_query = base_query.offset((page - 1) * page_size).limit(page_size)

        # Add ordering by creation date (newest first)
        base_query = base_query.order_by(KnowledgeBase.created_at.desc())

        # Execute query
        result = await self.session.execute(base_query)
        knowledge_bases = result.scalars().all()

        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
        has_next = page < total_pages
        has_previous = page > 1

        # Get integration details for each knowledge base
        kb_with_integrations = []
        for kb in knowledge_bases:
            # Get integration details
            integration_query = select(Integration).where(Integration.id == kb.integration_id)
            integration_result = await self.session.execute(integration_query)
            integration = integration_result.scalar_one_or_none()

            kb_data = {
                "id": kb.id,
                "name": kb.name,
                "state": kb.state.value,
                "created_at": kb.created_at,
                "last_indexed_at": kb.last_indexed_at,
                "source_identifier": kb.source_identifier,
                "created_by": kb.created_by,
                "integration": None,
                "is_updatable": kb.is_updatable
            }

            if integration:
                kb_data["integration"] = {
                    "id": integration.id,
                    "type": integration.type.name,
                    "name": integration.name,
                    "image_name": integration.image_name,
                    "integration_help_url": integration.integration_help_url
                }

            kb_with_integrations.append(kb_data)

        return {
            "knowledge_bases": kb_with_integrations,
            "pagination": {
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "has_next": has_next,
                "has_previous": has_previous,
            },
        }

    @latency(metric=DB_QUERY_LATENCY)
    async def update_kb_name_and_pat_url_branch(self, kb_id: int, name: Optional[str] = None, pat: Optional[str] = None,
                                     branch_name: Optional[str] = None, url: Optional[str] = None,
                                     commit: bool = True) -> None:
        """
        Update knowledge base name, PAT, branch name, and URL in settings_json.

        Args:
            kb_id: Knowledge base ID
            name: Optional new name for the knowledge base
            pat: Optional new Personal Access Token to store in settings_json
            branch_name: Optional new branch name to store in settings_json
            url: Optional new repository URL to store in settings_json
            commit: Whether to commit the transaction
        """
        # First get the current settings_json
        kb = await self.get_by_id(kb_id)
        if not kb:
            raise ValueError(f"Knowledge base with id {kb_id} not found")

        # Prepare update values
        update_values = {}

        # Update name if provided
        if name is not None:
            update_values["name"] = name

        # Update settings_json if any credential fields are provided
        if any(param is not None for param in [pat, branch_name, url]):
            updated_settings_json = kb.settings_json.copy() if kb.settings_json else {}

            # Ensure credentials dict exists
            if "credentials" not in updated_settings_json:
                updated_settings_json["credentials"] = {}

            # Update credentials with provided values
            if pat is not None:
                updated_settings_json["credentials"]["pat"] = pat

            if branch_name is not None:
                updated_settings_json["credentials"]["branch_name"] = branch_name

            if url is not None:
                updated_settings_json["credentials"]["url"] = url
                # Also update source_identifier if URL is changing
                update_values["source_identifier"] = url

            update_values["settings_json"] = updated_settings_json

        # Only proceed if there are values to update
        if update_values:
            stmt = (
                update(KnowledgeBase)
                .where(KnowledgeBase.id == kb_id)
                .values(**update_values)
            )
            await self.session.execute(stmt)
            if commit:
                await self.session.commit()


class IngestionRunDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=IngestionRun)

    @latency(metric=DB_QUERY_LATENCY)
    async def create_ingestion_run(self, **kwargs) -> IngestionRun:
        ingestion_run = IngestionRun(**kwargs)

        self.session.add(ingestion_run)
        await self.session.flush()
        return ingestion_run

    @latency(metric=DB_QUERY_LATENCY)
    async def update_run_summary(
        self,
        run_id: int,
        status: str,
        total_source_item: int,
        total_chunks: int,
        failed_chunk_elastic_doc_id: list[str],
    ):
        stmt = (
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                finished_at=datetime.utcnow(),
                status=status,
                stats_json={
                    "total_source_item": total_source_item,
                    "total_chunks": total_chunks,
                    "failed_chunk_elastic_doc_id": failed_chunk_elastic_doc_id,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

class SourceItemDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=SourceItem)

    async def bulk_insert(self, source_items: list[dict]):
        try:
            # Convert dictionaries to SourceItem objects
            items_to_insert = [SourceItem(**item) for item in source_items]

            # Add the items to the session in bulk
            self.session.add_all(items_to_insert)

            # Commit the transaction to persist the data
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Error occurred while bulk inserting source items: {str(e)}")

    @latency(metric=DB_QUERY_LATENCY)
    async def get_by_kb_id_and_path(self, kb_id: int, logical_path: str) -> Optional[SourceItem]:
        """Get source item by knowledge base ID and logical path"""
        stmt = (
            select(self.db_model)
            .where(
                self.db_model.kb_id == kb_id,
                self.db_model.logical_path == logical_path
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @latency(metric=DB_QUERY_LATENCY)
    async def delete_by_id(self, id: str) -> None:
        """Delete source item by ID"""
        try:
            stmt = delete(self.db_model).where(self.db_model.id == id)
            await self.session.execute(stmt)
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Error deleting source item: {str(e)}")

    @latency(metric=DB_QUERY_LATENCY)
    async def get_all_by_kb_id(self, kb_id: int) -> List[SourceItem]:
        """Get all source items for a specific knowledge base ID"""
        stmt = (
            select(self.db_model)
            .where(self.db_model.kb_id == kb_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

class ChunkDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=Chunk)

    @latency(metric=DB_QUERY_LATENCY)
    async def bulk_insert(self, chunks: list[dict]):
        try:
            # Convert dictionaries to SourceItem objects
            items_to_insert = [Chunk(**item) for item in chunks]

            # Add the items to the session in bulk
            self.session.add_all(items_to_insert)

            # Commit the transaction to persist the data
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Error occurred while bulk inserting source items: {str(e)}")

    @latency(metric=DB_QUERY_LATENCY)
    async def get_count_by_source_item_ids(self, source_item_ids: List[str]) -> int:
        """Get total count of chunks for given source item IDs"""
        stmt = (
            select(func.count())
            .select_from(self.db_model)
            .where(self.db_model.source_item_id.in_(source_item_ids))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

class IngestionErrorDao(BaseDao):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=IngestionError)

    @latency(metric=DB_QUERY_LATENCY)
    async def create_ingestion_error(self, commit: bool = True, **kwargs) -> IngestionError:
        error = IngestionError(**kwargs)
        self.session.add(error)
        await self.session.flush()

        if commit:
            await self.session.commit()
        return error