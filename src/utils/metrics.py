from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

REQUEST_COUNTER = Counter('http_requests_total', 'Total number of HTTP requests made', ['method', 'status', 'endpoint'])
REQUEST_HISTOGRAM = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        REQUEST_COUNTER.labels(method=request.method, status=response.status_code, endpoint=request.url.path).inc()
        REQUEST_HISTOGRAM.labels(method=request.method, endpoint=request.url.path).observe(duration)

        return response

def setup_metrics(app: FastAPI):
    app.add_middleware(PrometheusMiddleware)
    @app.get("/TrhBVe_m5gg2002_E5VVqS", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    