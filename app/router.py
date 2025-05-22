from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from config.settings import loaded_config
from kb.router import knowledge_base_router
from prometheus.metrics import REGISTRY
from app.routing import CustomRequestRoute
from starlette.responses import Response


async def healthz():
    return JSONResponse(status_code=200, content={"success": True})


api_router = APIRouter()

""" all version v1.0 routes """
api_router_v1 = APIRouter(prefix='/v1.0', route_class=CustomRequestRoute)


if loaded_config.server_type == "public":
    """ Declare your routes here """
    api_router_v1.include_router(knowledge_base_router)
elif loaded_config.server_type == "websocket":
    """ Declare your websockets here """
else:
    """ all common routes """

""" health check routes """
api_router_healthz = APIRouter()
api_router_healthz.add_api_route("/_healthz", methods=['GET'], endpoint=healthz, include_in_schema=False)
api_router_healthz.add_api_route("/_readyz", methods=['GET'], endpoint=healthz, include_in_schema=False)

api_router.include_router(api_router_healthz)
api_router.include_router(api_router_v1)


async def get_prometheus_data():
    """Endpoint that serves Prometheus metrics."""
    prom_response = Response(content=generate_latest(registry=REGISTRY))
    prom_response.headers["Content-Type"] = CONTENT_TYPE_LATEST
    return prom_response


prometheus_router = APIRouter()

prometheus_router.add_api_route("/metrics", methods=['GET'], endpoint=get_prometheus_data, include_in_schema=False)

api_router.include_router(prometheus_router)
