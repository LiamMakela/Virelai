import time

from fastapi import Request
from prometheus_client import Counter, Histogram


HTTP_REQUESTS = Counter(
    "virelai_api_http_requests_total",
    "Total HTTP requests handled by the Virelai API",
    [
        "method",
        "route",
        "status",
    ],
)


HTTP_REQUEST_DURATION = Histogram(
    "virelai_api_http_request_duration_seconds",
    "Virelai API HTTP request duration",
    [
        "method",
        "route",
    ],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2.5,
        5,
        10,
    ),
)


async def observe_http_request(
    request: Request,
    call_next,
):
    if request.url.path == "/metrics":
        return await call_next(request)

    started = time.perf_counter()

    status_code = "500"

    try:
        response = await call_next(
            request
        )

        status_code = str(
            response.status_code
        )

        return response

    finally:
        duration = (
            time.perf_counter()
            - started
        )

        route_object = (
            request.scope.get(
                "route"
            )
        )

        route = getattr(
            route_object,
            "path",
            "unmatched",
        )

        HTTP_REQUESTS.labels(
            method=request.method,
            route=route,
            status=status_code,
        ).inc()

        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            route=route,
        ).observe(
            duration
        )