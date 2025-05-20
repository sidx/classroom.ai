from kb.serializers import KnowledgeBaseRequest, GetVectorSearchRequest, GetKBStatusRequest, \
    ShareKnowledgeBaseRequest, GetKbRequest, UpdateKB
from kb.service import KnowledgeBaseService
from sqlalchemy.ext.asyncio import AsyncSession

from clerk_integration.utils import UserData
from utils.connection_handler import ConnectionHandler
from typing import List

from utils.serializers import ResponseData


class KnowledgeBaseView:
    def __init__(self, session: AsyncSession):
        self.knowledge_base_service = KnowledgeBaseService(session)

    async def start_loading(self, request: KnowledgeBaseRequest, connection_handler: ConnectionHandler, user_data: UserData) -> ResponseData:
        return await self.knowledge_base_service.start_loading(request, connection_handler, user_data)

    # async def get_vector_search(self, request: GetVectorSearchRequest) -> ResponseData:
    #     return await self.knowledge_base_service.get_vector_search(request)
    #
    # async def get_integrations(self) -> ResponseData:
    #     return await self.knowledge_base_service.get_integrations()
    #
    # async def get_indexing_status(self, user_data: UserData, request: GetKBStatusRequest) -> ResponseData:
    #     return await self.knowledge_base_service.get_indexing_status(user_data, request)
    #
    # async def delete_knowledge_bases(self, kb_ids: List[int], connection_handler: ConnectionHandler, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.delete_knowledge_bases(kb_ids, connection_handler, user_data)
    #
    # async def share_knowledge_bases(self, request: ShareKnowledgeBaseRequest, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.share_knowledge_bases(request, user_data)
    #
    # async def get_knowledge_bases(self, filter: GetKbRequest, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.get_knowledge_bases(filter, user_data)
    #
    # async def revoke_knowledge_base_access(self, request: ShareKnowledgeBaseRequest, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.revoke_knowledge_base_access(request, user_data)
    #
    # async def is_url_public(self, url: str, provider: str, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.is_url_public(url, provider, user_data)
    #
    # async def update_kb(self, request: UpdateKB, user_data: UserData) -> ResponseData:
    #     return await self.knowledge_base_service.update_knowledge_bases(request, user_data)
