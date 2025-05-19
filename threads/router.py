from fastapi import APIRouter

from app.routing import CustomRequestRoute
from threads.views import ThreadView, ThreadMessageView

threads_router_v1 = APIRouter(route_class=CustomRequestRoute, prefix='/threads')

threads_router_v1.add_api_route('/', methods=['GET'], endpoint=ThreadView.get_v1)
threads_router_v1.add_api_route('/', methods=['POST'], endpoint=ThreadView.post_v1)
threads_router_v1.add_api_route('/{thread_id}/', methods=['DELETE'], endpoint=ThreadView.delete_v1)

threads_router_v1.add_api_route('/messages/', methods=['POST'], endpoint=ThreadMessageView.post_v1)
threads_router_v1.add_api_route('/{thread_id}/messages/', methods=['PATCH'],
                                endpoint=ThreadMessageView.put_v1)
threads_router_v1.add_api_route('/thread/{thread_id}/messages/', methods=['GET'], endpoint=ThreadMessageView.get_v1)
threads_router_v1.add_api_route('/search', methods=['GET'], endpoint=ThreadMessageView.search_messages_v1)

threads_router_v2 = APIRouter(route_class=CustomRequestRoute, prefix='/threads')
#
threads_router_v2.add_api_route('/', methods=['GET'], endpoint=ThreadView.get_v2)
threads_router_v2.add_api_route('/', methods=['POST'], endpoint=ThreadView.post_v2)
threads_router_v2.add_api_route('/{thread_id}/', methods=['DELETE'], endpoint=ThreadView.delete_v2)

threads_router_v2.add_api_route('/messages/', methods=['POST'], endpoint=ThreadMessageView.post_v2)
threads_router_v2.add_api_route('/{thread_id}/messages/', methods=['PATCH'],
                                endpoint=ThreadMessageView.put_v2)
threads_router_v2.add_api_route('/thread/{thread_id}/messages/', methods=['GET'],
                                endpoint=ThreadMessageView.get_v2)
threads_router_v2.add_api_route('/search', methods=['GET'], endpoint=ThreadMessageView.search_messages_v2)


threads_router_v3 = APIRouter(route_class=CustomRequestRoute, prefix='/threads')
threads_router_v3.add_api_route('/', methods=['GET'], endpoint=ThreadView.get_v3)
threads_router_v3.add_api_route('/thread/{thread_id}/messages/', methods=['GET'],
                                endpoint=ThreadMessageView.get_v3)