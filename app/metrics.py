from datetime import datetime, timezone, timedelta
import json
from typing import Optional, Tuple
from app.database import get_db_connection

def get_time_range(conn, store_id: str, start: Optional[str] = None, end: Optional[str] = None, window: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    tz_kolkata = timezone(timedelta(hours=5, minutes=30))
    
    # If start/end are explicitly provided, prioritize them
    if start or end:
        return start, end

    # Fetch max event timestamp in DB
    row = conn.execute("SELECT max(timestamp) FROM events WHERE store_id = ?", (store_id,)).fetchone()
    max_ts_str = row[0] if row and row[0] is not None else None
    
    if max_ts_str:
        max_dt_utc = datetime.fromisoformat(max_ts_str.replace("Z", "+00:00"))
        max_dt_local = max_dt_utc.astimezone(tz_kolkata)
    else:
        max_dt_local = datetime.now(tz_kolkata)
        max_dt_utc = datetime.now(timezone.utc)
        
    if not window:
        window = "latest_day"
        
    if window == "latest_day":
        bus_date = max_dt_local.date()
        start_local = datetime.combine(bus_date, datetime.min.time()).replace(tzinfo=tz_kolkata)
        end_local = datetime.combine(bus_date, datetime.max.time()).replace(tzinfo=tz_kolkata)
        return (
            start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        
    elif window == "today":
        today_local = datetime.now(tz_kolkata).date()
        start_local = datetime.combine(today_local, datetime.min.time()).replace(tzinfo=tz_kolkata)
        end_local = datetime.combine(today_local, datetime.max.time()).replace(tzinfo=tz_kolkata)
        return (
            start_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        
    elif window == "last_60m":
        start_dt = max_dt_utc - timedelta(minutes=60)
        return (
            start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            max_dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        
    return None, None

def calculate_conversions(
    conn,
    store_id: str,
    visitors: list[str],
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None
) -> set[str]:
    if not visitors:
        return set()
        
    # Get all transactions
    txns_query = "SELECT transaction_id, timestamp FROM transactions WHERE store_id = ?"
    txns_params = [store_id]
    if start_ts:
        txns_query += " AND timestamp >= ?"
        txns_params.append(start_ts)
    if end_ts:
        txns_query += " AND timestamp <= ?"
        txns_params.append(end_ts)
        
    txns = conn.execute(txns_query, txns_params).fetchall()
    if not txns:
        return set()
        
    # Get all billing counter events for these visitors
    billing_events = []
    for visitor in visitors:
        be_query = """
            SELECT timestamp FROM events 
            WHERE store_id = ? AND visitor_id = ? AND zone_id = 'BILLING_COUNTER' AND is_staff = 0
        """
        be_params = [store_id, visitor]
        if start_ts:
            be_query += " AND timestamp >= ?"
            be_params.append(start_ts)
        if end_ts:
            be_query += " AND timestamp <= ?"
            be_params.append(end_ts)
            
        rows = conn.execute(be_query, be_params).fetchall()
        for r in rows:
            dt = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            billing_events.append((visitor, dt))
            
    # Pair transactions with billing visits
    potential_pairs = []
    for txn in txns:
        txn_id = txn["transaction_id"]
        txn_dt = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
        
        for visitor, be_dt in billing_events:
            diff = (txn_dt - be_dt).total_seconds()
            if 0 <= diff <= 300: # 0 to 5 minutes before transaction
                potential_pairs.append((diff, txn_id, visitor))
                
    # Sort pairs by time difference ascending (closest first)
    potential_pairs.sort(key=lambda x: x[0])
    
    assigned_txns = set()
    converted_sessions = set()
    
    for diff, txn_id, visitor in potential_pairs:
        if txn_id not in assigned_txns and visitor not in converted_sessions:
            assigned_txns.add(txn_id)
            converted_sessions.add(visitor)
            
    return converted_sessions



def get_store_metrics(store_id: str, start: Optional[str] = None, end: Optional[str] = None, window: Optional[str] = None) -> dict:
    conn = get_db_connection()
    try:
        start_ts, end_ts = get_time_range(conn, store_id, start, end, window)
        
        # Base filters for query
        event_filter = "store_id = ? AND is_staff = 0"
        event_params = [store_id]
        
        if start_ts:
            event_filter += " AND timestamp >= ?"
            event_params.append(start_ts)
        if end_ts:
            event_filter += " AND timestamp <= ?"
            event_params.append(end_ts)
            
        # Get unique visitors
        visitors_query = f"SELECT DISTINCT visitor_id FROM events WHERE {event_filter}"
        visitors = [r["visitor_id"] for r in conn.execute(visitors_query, event_params).fetchall()]
        unique_visitors = len(visitors)
        
        # Calculate conversions using the closest-pairing matching algorithm
        converted_visitors = calculate_conversions(conn, store_id, visitors, start_ts, end_ts)
        conversions = len(converted_visitors)
        conversion_rate = conversions / unique_visitors if unique_visitors > 0 else 0.0
        
        # Average dwell per zone
        dwell_query = f"""
            SELECT zone_id, avg(dwell_ms) as avg_dwell FROM events 
            WHERE {event_filter} AND zone_id IS NOT NULL
            GROUP BY zone_id
        """
        dwells = conn.execute(dwell_query, event_params).fetchall()
        avg_dwell_ms_by_zone = {r["zone_id"]: round(r["avg_dwell"], 2) for r in dwells}
        
        # Current Queue depth
        queue_query = f"""
            SELECT max(CAST(json_extract(metadata_json, '$.queue_depth') AS INTEGER)) as max_queue 
            FROM events 
            WHERE {event_filter} AND event_type = 'BILLING_QUEUE_JOIN'
        """
        max_queue = conn.execute(queue_query, event_params).fetchone()["max_queue"]
        current_queue_depth = max_queue if max_queue is not None else 0
        
        # Calculate Abandonment Rate:
        # Number of sessions that entered BILLING_COUNTER but did not make a purchase
        billing_query = f"""
            SELECT DISTINCT visitor_id FROM events 
            WHERE {event_filter} AND zone_id = 'BILLING_COUNTER'
        """
        billing_visitors = [r["visitor_id"] for r in conn.execute(billing_query, event_params).fetchall()]
        unique_billing = len(billing_visitors)
        
        abandoned_count = 0
        if unique_billing > 0:
            converted_billing = calculate_conversions(conn, store_id, billing_visitors, start_ts, end_ts)
            abandoned_count = unique_billing - len(converted_billing)
                
        abandonment_rate = abandoned_count / unique_billing if unique_billing > 0 else 0.0
        
        # Last event timestamp
        last_event_query = f"SELECT max(timestamp) FROM events WHERE {event_filter}"
        last_event_ts = conn.execute(last_event_query, event_params).fetchone()[0]
        
        return {
            "store_id": store_id,
            "window_start": start_ts,
            "window_end": end_ts,
            "unique_visitors": unique_visitors,
            "conversion_rate": round(conversion_rate, 4),
            "avg_dwell_ms_by_zone": avg_dwell_ms_by_zone,
            "current_queue_depth": current_queue_depth,
            "abandonment_rate": round(abandonment_rate, 4),
            "last_event_timestamp": last_event_ts
        }
    finally:
        conn.close()

