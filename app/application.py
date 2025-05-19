import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from config.sentry import configure_sentry
from app.router import api_router
from prometheus.helper import generate_prometheus_data
from utils.custom_middleware import PrometheusMiddleware, SecurityHeadersMiddleware
from utils.load_config import run_on_startup, run_on_exit
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from utils.constants import PROMETHEUS_LOG_TIME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from opentelemetry.instrumentation import asgi


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_on_startup()
    yield
    await run_on_exit()


async def repeated_task_for_prometheus():
    while True:
        await generate_prometheus_data()
        await asyncio.sleep(PROMETHEUS_LOG_TIME)


def get_app() -> FastAPI:
    class PatchedASGIGetter(asgi.ASGIGetter):
        def keys(self, carrier):
            print("keys")
            headers = carrier.get("headers") or []
            return [_key.decode("utf8") for (_key, _value) in headers]

    asgi.asgi_getter = PatchedASGIGetter()
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    # if loaded_config.sentry_dsn:
    # Enables sentry integration.
    configure_sentry()

    almanac_app = FastAPI(
        debug=True,
        title="almanac",
        docs_url=None,
        openapi_url="/openapi.json",
        # default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    # Configure CORS to allow only 'wmsz0.de'
    almanac_app.add_middleware(
        CORSMiddleware,
        # allow_origins=["*"],  # Only allow this origins
        allow_origins=[],  # Only allow this origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    almanac_app.include_router(api_router)
    almanac_app.add_middleware(SessionMiddleware, secret_key="** Session Middleware **")
    almanac_app.add_middleware(PrometheusMiddleware)
    almanac_app.add_middleware(SecurityHeadersMiddleware)

    FastAPIInstrumentor.instrument_app(almanac_app)
    return almanac_app
