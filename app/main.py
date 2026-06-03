from fastapi import FastAPI, HTTPException, status, Response, Request
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from typing import Optional
import json
import os
import time
import uuid
from datetime import datetime, timezone

from app.models import EventModel
from app.database import init_db, get_db_connection, check_db_health
from app.pos import load_and_normalize_pos
from app.metrics import get_store_metrics
from app.funnel import get_store_funnel
from app.heatmap import get_store_heatmap
from app.anomalies import get_store_anomalies
from app.logging_config import setup_logging, log_request

app = FastAPI(title="Store Intelligence API")

# Mount dashboard static files
# Enable html=True so index.html serves as /dashboard root
dashboard_dir = os.path.join(os.path.dirname(__file__), "../dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    
    # Try to extract store_id from request path
    store_id = None
    path_parts = request.url.path.split("/")
    if "stores" in path_parts:
        idx = path_parts.index("stores")
        if idx + 1 < len(path_parts):
            store_id = path_parts[idx + 1]
            
    response = await call_next(request)
    
    latency_ms = (time.time() - start_time) * 1000.0
    response.headers["X-Trace-Id"] = trace_id
    
    event_count = getattr(request.state, "event_count", None)
    
    log_request(
        trace_id=trace_id,
        endpoint=request.url.path,
        status_code=response.status_code,
        latency_ms=latency_ms,
        store_id=store_id,
        event_count=event_count
    )
    return response

@app.on_event("startup")
def startup_event():
    # 0. Setup logger
    setup_logging()
    
    # 1. Initialize Database Tables
    init_db()
    
    # 2. Check if transactions table is empty, and seed it from POS csv
    conn = get_db_connection()
    try:
        count = conn.execute("SELECT count(*) FROM transactions").fetchone()[0]
        if count == 0:
            csv_path = os.path.join(os.path.dirname(__file__), "../Brigade_Bangalore_10_April_26.csv")
            if os.path.exists(csv_path):
                txns = load_and_normalize_pos(csv_path)
                for t in txns:
                    conn.execute("""
                        INSERT OR IGNORE INTO transactions 
                        (transaction_id, store_id, timestamp, basket_value_inr, item_count, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        t["transaction_id"], t["store_id"], t["timestamp"],
                        t["basket_value_inr"], t["item_count"], t["metadata_json"]
                    ))
                conn.commit()
    finally:
        conn.close()

@app.get("/health")
def health_check(response: Response):
    if not check_db_health():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unreachable"}

    conn = get_db_connection()
    try:
        # Check total events
        total_events = conn.execute("SELECT count(*) FROM events").fetchone()[0]
        
        # Check last event timestamp and ingest created_at
        last_event_row = conn.execute("SELECT max(timestamp) as max_ts, max(created_at) as max_created FROM events").fetchone()
        
        last_event_ts = last_event_row["max_ts"]
        last_ingest_ts = last_event_row["max_created"]
        
        stale_feed = False
        if last_ingest_ts:
            try:
                # clean 'Z' to parse ISO format
                clean_ts = last_ingest_ts.replace("Z", "+00:00")
                ingest_dt = datetime.fromisoformat(clean_ts)
                now_utc = datetime.now(timezone.utc)
                time_diff = now_utc - ingest_dt
                if time_diff.total_seconds() > 600: # 10 minutes
                    stale_feed = True
            except Exception:
                pass
                
        return {
            "status": "ok",
            "database": "ok",
            "total_events": total_events,
            "last_event_timestamp": last_event_ts,
            "last_ingest_timestamp": last_ingest_ts,
            "stale_feed": stale_feed
        }
    finally:
        conn.close()

@app.post("/events/ingest")
async def ingest_events(request: Request):
    body = await request.body()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
        
    raw_events = []
    if isinstance(data, list):
        raw_events = data
    elif isinstance(data, dict) and "events" in data:
        raw_events = data["events"]
    else:
        raise HTTPException(status_code=422, detail="Request body must be a list of events or a dict containing 'events'")

    if len(raw_events) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 500 events")

    request.state.event_count = len(raw_events)

    accepted = 0
    duplicates = 0
    rejected = 0
    errors = []

    conn = get_db_connection()
    try:
        for idx, item in enumerate(raw_events):
            try:
                event = EventModel(**item)
                
                # Check duplicate by event_id (idempotency)
                exists = conn.execute("SELECT 1 FROM events WHERE event_id = ?", (event.event_id,)).fetchone()
                if exists:
                    duplicates += 1
                    continue
                
                metadata_str = json.dumps(event.metadata) if event.metadata is not None else None
                conn.execute("""
                    INSERT INTO events 
                    (event_id, store_id, camera_id, visitor_id, event_type, timestamp, zone_id, dwell_ms, is_staff, confidence, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, event.store_id, event.camera_id, event.visitor_id,
                    event.event_type, event.timestamp, event.zone_id, event.dwell_ms,
                    1 if event.is_staff else 0, event.confidence, metadata_str
                ))
                accepted += 1
            except ValidationError as ve:
                rejected += 1
                eid = item.get("event_id") if isinstance(item, dict) else None
                errors.append({
                    "index": idx,
                    "event_id": eid,
                    "message": ve.errors()[0]["msg"] if ve.errors() else "Validation error"
                })
            except Exception as e:
                rejected += 1
                eid = item.get("event_id") if isinstance(item, dict) else None
                errors.append({
                    "index": idx,
                    "event_id": eid,
                    "message": str(e)
                })
        conn.commit()
    finally:
        conn.close()

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "errors": errors
    }

@app.get("/stores/{store_id}/metrics")
def get_store_metrics_endpoint(
    store_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    window: Optional[str] = None
):
    try:
        return get_store_metrics(store_id, start, end, window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stores/{store_id}/funnel")
def get_store_funnel_endpoint(
    store_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    window: Optional[str] = None
):
    try:
        return get_store_funnel(store_id, start, end, window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stores/{store_id}/heatmap")
def get_store_heatmap_endpoint(
    store_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    window: Optional[str] = None
):
    try:
        return get_store_heatmap(store_id, start, end, window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stores/{store_id}/anomalies")
def get_store_anomalies_endpoint(store_id: str):
    try:
        return get_store_anomalies(store_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

