import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus.metrics import REQUEST_LATENCY


#
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()  # More precise timing
        try:
            response = await call_next(request)
        except Exception as e:
            response = Response("Internal Server Error", status_code=500)
            raise e
        finally:
            process_time = time.perf_counter() - start_time
            route = request.scope.get("route")
            route_path = route.path if route else request.url.path
            REQUEST_LATENCY.labels(request.method, route_path).observe(process_time)
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
        return response
