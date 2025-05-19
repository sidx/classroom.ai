import time
from uuid import uuid4

import orjson
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_400_BAD_REQUEST
from typing import Callable
from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.routing import APIRoute

from prometheus.metrics import API_REQUEST_LATENCY, API_REQUESTS_COUNTER, ROUTE_REQUESTS_COUNTER
from utils.common import UserData
from utils.serializers import ResponseData
from utils.exceptions import ApiException
from config.logging import logger
from starlette.responses import StreamingResponse
from starlette.templating import _TemplateResponse


class CustomRequestRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            request_data = await process_request_data(request)
            start_time = time.perf_counter()

            try:
                process_request_headers(request, request_data)
                response = await original_route_handler(request)
                response_data = process_response(response, request_data, start_time)
                log_metrics_and_request(request, request_data, response_data, start_time)
                return response

            except (orjson.JSONDecodeError, ApiException) as exc:
                return handle_exception(request, request_data, exc, HTTP_400_BAD_REQUEST, start_time)
            except (RequestValidationError, ValidationError) as exc:
                errors = format_pydantic_errors(exc)
                return handle_exception(request, request_data, errors, HTTP_400_BAD_REQUEST, start_time)
            except HTTPException as exc:
                return handle_exception(request, request_data, exc.detail, exc.status_code, start_time)
            except Exception as exc:
                return handle_exception(request, request_data, exc, HTTP_500_INTERNAL_SERVER_ERROR, start_time)

        return custom_route_handler


async def process_request_data(request: Request) -> dict:
    request_data = {
        'client_host': request.client,
        'url': request.url.components,
        'url_path': request.scope['route'].path,
        'request_method': request.method,
        'path_params': request.path_params.items(),
        'query_params': request.query_params.items(),
        'headers': request.headers.items(),
        'request_body': await request.body()
    }
    return request_data


def request_exception_handler(method=None, url_path=None, request_data=None, exc=None, start_time=None,
                              status_code=None) -> Response:
    request_data["error"] = exc if isinstance(exc, list) else [str(exc)]
    end_time = time.perf_counter()
    request_data['request_duration'] = end_time - start_time
    logger.exception("Exception occurred for %s", request_data['url_path'])
    error_response = ResponseData.construct(errors=request_data["error"], success=False).dict()
    try:
        sanitized_method = sanitize_label(method)
        sanitized_url_path = sanitize_label(url_path)
        sanitized_status_code = sanitize_label(status_code)
        API_REQUEST_LATENCY.labels(method=sanitized_method, url_path=sanitized_url_path,
                                status_code=status_code).observe(end_time - start_time)
        API_REQUESTS_COUNTER.labels(method=sanitized_method, url_path=sanitized_url_path,
                                    status_code=status_code).inc()
        ROUTE_REQUESTS_COUNTER.labels(method=sanitized_method,route=sanitized_url_path,
                                status_code=sanitized_status_code).inc()
    except Exception as e:
        print("ERROR: Prometheus error - %s", e)
    return ORJSONResponse(content=error_response, status_code=status_code)


def get_formatted_pydantic_errors(validation_error: ValidationError):
    formatted_validation_errors = [{
        "msg": f"{error['loc'][-1]}: {error['msg']}",
        "location": error['loc']
    } for error in validation_error.errors()]
    return formatted_validation_errors


def sanitize_label(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        value = str(value)
    return value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

def handle_exception(request, request_data, exc, status_code, start_time):
    request_data["error"] = [str(exc)] if not isinstance(exc, list) else exc
    end_time = time.perf_counter()
    request_data['request_duration'] = end_time - start_time
    logger.exception("Exception occurred for %s", request_data['url_path'], extra={'request_data': request_data})
    error_response = ResponseData.construct(errors=request_data["error"], success=False).dict()
    response_object = {
        'status_code': status_code,
        "error_response":error_response
    }
    log_metrics_and_request(request,request_data, response_object, start_time)
    return ORJSONResponse(content=error_response, status_code=status_code)


def format_pydantic_errors(validation_error: ValidationError):
    return [
        {"msg": f"{error['loc'][-1]}: {error['msg']}", "location": error['loc']}
        for error in validation_error.errors()
    ]


def process_request_headers(request: Request, request_data: dict):
    content_type = request.headers.get("content-type")
    request_data['request_body'] = (
        orjson.loads(request_data['request_body'])
        if request_data['request_body'] and not content_type.startswith("multipart/form-data")
        else {}
    )
    if x_user_data := request.headers.get("x-user-data"):
        request.state.user_data = UserData.construct(**orjson.loads(x_user_data))


def process_response(response: Response, request_data: dict, start_time: float) -> dict:
    end_time = time.perf_counter()
    request_data['request_duration'] = end_time - start_time

    if isinstance(response, StreamingResponse):
        return {'status_code': response.status_code, 'body': {'data': 'streaming response', 'identifier': str(uuid4())}}
    if isinstance(response, _TemplateResponse):
        return {'status_code': response.status_code, 'body': "HTML response"}
    return {'status_code': response.status_code, 'body': orjson.loads(response.body.decode('utf-8')) if response.body else ''}


def log_metrics_and_request(request, request_data, response_data, start_time):
    try:
        sanitized_method = sanitize_label(request.method)
        sanitized_url_path = sanitize_label(request_data.get('url_path', 'unknown'))
        sanitized_status_code = sanitize_label(response_data['status_code'])

        end_time = time.perf_counter()
        API_REQUEST_LATENCY.labels(method=sanitized_method, url_path=sanitized_url_path, status_code=sanitized_status_code,service_name="cerebrum").observe(end_time - start_time)
        API_REQUESTS_COUNTER.labels(method=sanitized_method, url_path=sanitized_url_path, status_code=sanitized_status_code,service_name="cerebrum").inc()
        ROUTE_REQUESTS_COUNTER.labels(method=sanitized_method, route=sanitized_url_path, status_code=sanitized_status_code,service_name="cerebrum").inc()

        consumed_time = end_time - start_time
        log_api_requests_to_gcp(request_data, response_data, consumed_time)
    except Exception as e:
        logger.error("Prometheus Error: %s", e)

def log_api_requests_to_gcp(request_data, response_data, consumed_time):
    api_logs = {
        "status": response_data['status_code'],
        'consumed_time': consumed_time or 0,
        'request': request_data,
        'response': response_data
    }
    if response_data['status_code'] == 200:
        logger.info(api_logs)
    else:
        logger.error(api_logs)
