import time
import traceback
from functools import wraps
from fastapi import status

from sqlalchemy.exc import OperationalError

from app.routing import sanitize_label
from prometheus.metrics import DEADLOCK_COUNTER, FAILED_QUERIES_COUNTER, SLOW_QUERIES_COUNTER, DB_QUERY_LATENCY
from config.logging import logger
from app.routing import log_api_requests_to_gcp


def latency(metric, **label_kwargs):
    """
    Enhanced decorator that tracks query latency, identifies slow queries,
    and monitors deadlocks
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            elapsed_time = 0
            if func.__name__:
                query_type_string = func.__name__
            else:
                query_type_string = 'unknown'
            try:
                result = await func(*args, **kwargs)
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time
                log_api_requests_to_gcp({"DAO function": query_type_string}, {"db_result":result, "status_code": status.HTTP_200_OK}, elapsed_time)
                try:
                    if elapsed_time > 0.2:
                        SLOW_QUERIES_COUNTER.labels(
                            query_type=sanitize_label(query_type_string),
                            service_name="almanac"
                        ).inc()
                    DB_QUERY_LATENCY.labels(
                        query=sanitize_label(query_type_string),
                        service_name="almanac"
                    ).observe(elapsed_time)
                except Exception as prometheus_exp:
                    logger.error(str(prometheus_exp))
                    logger.error(traceback.format_exc())
                    return result

                return result
            except OperationalError as exp:
                log_api_requests_to_gcp({"DAO function": query_type_string}, {"db_error": exp, "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR}, 0)
                if "deadlock detected" in str(exp).lower():
                    DEADLOCK_COUNTER.labels(
                        query=sanitize_label(query_type_string),
                        service_name="almanac"
                    ).inc()

                FAILED_QUERIES_COUNTER.labels(
                    query_type=sanitize_label(query_type_string),
                    service_name="almanac"
                ).inc()
                logger.error("Exception in latency decorator", str(exp))
                logger.error(traceback.format_exc())
                raise exp
            except Exception as exp:
                log_api_requests_to_gcp({"DAO function": query_type_string}, {"db_error":exp, "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR}, 0)
                FAILED_QUERIES_COUNTER.labels(
                    query_type=sanitize_label(query_type_string),
                    service_name="almanac"
                ).inc()
                logger.error("Exception in latency decorator", str(exp))
                logger.error(traceback.format_exc())
                raise exp

        return wrapper

    return decorator