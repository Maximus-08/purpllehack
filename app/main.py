from fastapi import FastAPI, HTTPException, status, Response, Request
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from typing import Optional
import json
import os
from datetime import datetime, timezone

from app.models import EventModel
from app.database import init_db, get_db_connection, check_db_health
from app.pos import load_and_normalize_pos

app = FastAPI(title="Store Intelligence API")

# Mount dashboard static files
# Enable html=True so index.html serves as /dashboard root
dashboard_dir = os.path.join(os.path.dirname(__file__), "../dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")

@app.on_event("startup")
def startup_event():
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
def get_store_metrics(store_id: str, start: Optional[str] = None, end: Optional[str] = None):
    conn = get_db_connection()
    try:
        # Get unique visitors (non-staff)
        visitors_query = "SELECT DISTINCT visitor_id FROM events WHERE store_id = ? AND is_staff = 0"
        params = [store_id]
        if start:
            visitors_query += " AND timestamp >= ?"
            params.append(start)
        if end:
            visitors_query += " AND timestamp <= ?"
            params.append(end)
            
        visitors = [r["visitor_id"] for r in conn.execute(visitors_query, params).fetchall()]
        unique_visitors = len(visitors)
        
        # Calculate conversions
        conversions = 0
        if unique_visitors > 0:
            txns_query = "SELECT timestamp FROM transactions WHERE store_id = ?"
            txns = conn.execute(txns_query, [store_id]).fetchall()
            
            converted_sessions = set()
            for visitor in visitors:
                billing_events_query = """
                    SELECT timestamp FROM events 
                    WHERE store_id = ? AND visitor_id = ? AND zone_id = 'BILLING_COUNTER' AND is_staff = 0
                """
                billing_events = conn.execute(billing_events_query, [store_id, visitor]).fetchall()
                
                for be in billing_events:
                    be_ts = datetime.fromisoformat(be["timestamp"].replace("Z", "+00:00"))
                    for txn in txns:
                        txn_ts = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
                        diff_seconds = (txn_ts - be_ts).total_seconds()
                        if 0 <= diff_seconds <= 300: # 0 to 5 minutes before txn
                            converted_sessions.add(visitor)
                            break
            conversions = len(converted_sessions)
            
        conversion_rate = conversions / unique_visitors if unique_visitors > 0 else 0.0
        
        # Average dwell per zone
        dwell_query = """
            SELECT zone_id, avg(dwell_ms) as avg_dwell FROM events 
            WHERE store_id = ? AND zone_id IS NOT NULL AND is_staff = 0
            GROUP BY zone_id
        """
        dwells = conn.execute(dwell_query, [store_id]).fetchall()
        avg_dwell_ms_by_zone = {r["zone_id"]: round(r["avg_dwell"], 2) for r in dwells}
        
        # Current Queue depth
        queue_query = """
            SELECT max(CAST(json_extract(metadata_json, '$.queue_depth') AS INTEGER)) as max_queue 
            FROM events 
            WHERE store_id = ? AND event_type = 'BILLING_QUEUE_JOIN' AND is_staff = 0
        """
        max_queue = conn.execute(queue_query, [store_id]).fetchone()["max_queue"]
        current_queue_depth = max_queue if max_queue is not None else 0
        
        # Last event timestamp
        last_event_ts = conn.execute("SELECT max(timestamp) FROM events WHERE store_id = ?", [store_id]).fetchone()[0]
        
        return {
            "store_id": store_id,
            "unique_visitors": unique_visitors,
            "conversion_rate": conversion_rate,
            "avg_dwell_ms_by_zone": avg_dwell_ms_by_zone,
            "current_queue_depth": current_queue_depth,
            "abandonment_rate": 0.0,
            "last_event_timestamp": last_event_ts
        }
    finally:
        conn.close()
