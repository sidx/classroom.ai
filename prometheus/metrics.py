import os
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client import CollectorRegistry
from prometheus_client import multiprocess  # Import the multiprocess module

REGISTRY = CollectorRegistry()
buckets = [0.1, 0.25, 0.5, 0.75, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12.5, 15, 20, 25, 30, 60]
# if 'prometheus_multiproc_dir' in os.environ or 'PROMETHEUS_MULTIPROC_DIR' in os.environ:
#     multiprocess.MultiProcessCollector(REGISTRY)  # Add this line to enable multiprocess support

# API Request Metrics
API_REQUEST_LATENCY = Histogram(
    'cerebrum_http_request_received_duration_seconds',
    'Cerebrum API request Latency',
    ["method", "url_path", "status_code","service_name"],
    registry=REGISTRY,
    buckets=buckets
)

API_REQUESTS_COUNTER = Counter(
    "api_requests_count",
    "Total number of shipment api requests",
    ["method", "url_path", "status_code","service_name"],
    registry=REGISTRY
)

# CONCURRENT_REQUESTS = Gauge(
#     'concurrent_requests',
#     'Number of concurrent requests being processed',
#     ['method', 'url_path'],
#     registry=REGISTRY
# )

ROUTE_REQUESTS_COUNTER = Counter(
    "route_requests_total",
    "Total number of requests per route",
    ["method", "route", "status_code","service_name"],
    registry=REGISTRY
)

# Database Metrics
DB_QUERY_LATENCY = Histogram(
    'cerebrum_db_query_received_duration_seconds',
    'Query Latency',
    ['query',"service_name"],
    registry=REGISTRY,
    buckets=buckets
)

SLOW_QUERIES_COUNTER = Counter(
    'db_slow_queries_total',
    'Total number of slow queries',
    ['query_type',"service_name"],
    registry=REGISTRY
)

FAILED_QUERIES_COUNTER = Counter(
    'db_failed_queries_total',
    'Total number of failed database queries',
    ['query_type',"service_name"],
    registry=REGISTRY
)

DEADLOCK_COUNTER = Counter(
    'db_deadlocks_total',
    'Total number of deadlocks encountered',
    ['query',"service_name"],
    registry=REGISTRY
)

# Kafka metrics
KAFKA_CONSUMER_EVENT_LATENCY = Histogram(
    "cerebrum_consumer_message_processing_duration_seconds",
    "Latency of Kafka consumer event processing in seconds",
    ["topic","service_name","group_id"],
    registry=REGISTRY,
    buckets=buckets  # Adjust buckets as needed
)
KAFKA_PRODUCER_EVENT_LATENCY = Histogram(
    "cerebrum_producer_message_processing_duration_seconds",
    "Latency of Kafka producer event processing in seconds",
    ["topic","service_name"],
    registry=REGISTRY,
    buckets=buckets  # Adjust buckets as needed
)


# Define a Prometheus counter for exceptions
EXCEPTION_COUNTER = Counter(
    'exception_count',
    'Count of exceptions with details',
    ['exception_type', 'code'],
registry=REGISTRY
)


# The counter is labeled with 'email_id' and 'last_message' to capture specific retry counts
SURFACE_ASK_RETRY_COUNTER = Counter(
    'surface_ask_retry_counter',
    'Number of retries for API requests',
    ['email_id', 'last_message'],
registry=REGISTRY
)

REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "route"] , # Change 'endpoint' to 'route' for normalization,
        buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0,2.0,3.0,4.0],  # Buckets in seconds (1ms to 1s)
registry=REGISTRY


)
