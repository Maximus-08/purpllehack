import logging
import json
from typing import Optional

def setup_logging():
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # We output only the raw message, which will be our JSON string
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

def log_request(
    trace_id: str,
    endpoint: str,
    status_code: int,
    latency_ms: float,
    store_id: Optional[str] = None,
    event_count: Optional[int] = None
):
    log_data = {
        "trace_id": trace_id,
        "endpoint": endpoint,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 2)
    }
    if store_id:
        log_data["store_id"] = store_id
    if event_count is not None:
        log_data["event_count"] = event_count
        
    logger = logging.getLogger("app")
    logger.info(json.dumps(log_data))

