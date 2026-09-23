"""Origin timings without recording SQL, query parameters or user identifiers."""

import logging
from time import perf_counter

from django.db import connection


logger = logging.getLogger("performance")


class ApiTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        sql_ms = 0.0
        sql_count = 0

        def measure(execute, sql, params, many, context):
            nonlocal sql_ms, sql_count
            started = perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                sql_ms += (perf_counter() - started) * 1000
                sql_count += 1

        started = perf_counter()
        with connection.execute_wrapper(measure):
            response = self.get_response(request)
        elapsed_ms = (perf_counter() - started) * 1000
        response["Server-Timing"] = (
            f'app;dur={elapsed_ms:.1f};desc="Origin generation", '
            f'db;dur={sql_ms:.1f}, sql;desc="{sql_count} queries"'
        )
        if elapsed_ms >= 1000:
            match = getattr(request, "resolver_match", None)
            logger.warning(
                "slow_api route=%s status=%s app_ms=%.1f db_ms=%.1f sql_count=%s",
                getattr(match, "route", "unresolved"), response.status_code, elapsed_ms, sql_ms, sql_count,
            )
        return response
