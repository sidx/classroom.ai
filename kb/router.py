from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.routing import CustomRequestRoute
from config.settings import loaded_config
from kb.serializers import KnowledgeBaseRequest, GetVectorSearchRequest, DeleteKnowledgeBasesRequest, \
    GetKBStatusRequest, ShareKnowledgeBaseRequest, GetKbRequest, UpdateKB
from kb.views import KnowledgeBaseView
from utils.common import get_user_data_from_request
from utils.connection_handler import get_connection_handler_for_app


knowledge_base_router = APIRouter(prefix='/kb', route_class=CustomRequestRoute)

async def get_session() -> AsyncSession:
    session_factory = loaded_config.connection_manager.get_session_factory()
    async with session_factory() as session:
        yield session

async def get_knowledge_base_view(session: AsyncSession = Depends(get_session)) -> KnowledgeBaseView:
    return KnowledgeBaseView(session)

@knowledge_base_router.post("/start-loading")
async def start_loading(
    request: KnowledgeBaseRequest = Body(...),
    view: KnowledgeBaseView = Depends(get_knowledge_base_view),
    connection_handler = Depends(get_connection_handler_for_app),
    user_data = Depends(get_user_data_from_request),

):
    return await view.start_loading(request, connection_handler, user_data)

# @knowledge_base_router.post("/vector-search")
# async def get_vector_search(
#         request: GetVectorSearchRequest = Body(...),
#         view: KnowledgeBaseView = Depends(get_knowledge_base_view)
# ):
#     return await view.get_vector_search(request)
#
# @knowledge_base_router.get("/get-integrations")
# async def get_integrations(
#         view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#         user_data = Depends(get_user_data_from_request),
# ):
#     return await view.get_integrations()
#
# @knowledge_base_router.post("/status")
# async def get_indexing_status(
#     request: GetKBStatusRequest = Body(...),
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.get_indexing_status(user_data, request)
#
# @knowledge_base_router.delete("/delete-kbs")
# async def delete_knowledge_bases(
#     request: DeleteKnowledgeBasesRequest,
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     connection_handler = Depends(get_connection_handler_for_app),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.delete_knowledge_bases(request.kb_ids, connection_handler, user_data)
#
# @knowledge_base_router.post("/share")
# async def share_knowledge_bases(
#     request: ShareKnowledgeBaseRequest = Body(...),
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.share_knowledge_bases(request, user_data)
#
# @knowledge_base_router.post("/filter")
# async def get_knowledge_bases(
#     filter: GetKbRequest = Body(...),
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.get_knowledge_bases(filter, user_data)
#
# @knowledge_base_router.post("/revoke")
# async def revoke_knowledge_base_access(
#     request: ShareKnowledgeBaseRequest = Body(...),
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.revoke_knowledge_base_access(request, user_data)
#
# @knowledge_base_router.get("/is-url-public/{provider}")
# async def is_url_public(
#     url: str,
#     provider: str,
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.is_url_public(url, provider, user_data)
#
# @knowledge_base_router.post("/update")
# async def update_kb(
#     request: UpdateKB = Body(...),
#     view: KnowledgeBaseView = Depends(get_knowledge_base_view),
#     user_data = Depends(get_user_data_from_request),
# ):
#     return await view.update_kb(request, user_data)
