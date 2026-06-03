import os
import json
from typing import Optional
from app.database import get_db_connection
from app.metrics import get_time_range

LAYOUT_PATH = os.path.join(os.path.dirname(__file__), "../data/store_layout.json")

def load_zones() -> dict:
    if not os.path.exists(LAYOUT_PATH):
        return {}
    with open(LAYOUT_PATH, "r") as f:
        data = json.load(f)
        return data.get("zones", {})

def get_store_heatmap(store_id: str, start: Optional[str] = None, end: Optional[str] = None, window: Optional[str] = None) -> dict:
    conn = get_db_connection()
    try:
        start_ts, end_ts = get_time_range(conn, store_id, start, end, window)
        
        # Load all zones from layout to ensure 0-visit zones are included
        layout_zones = load_zones()
        
        # Base filters
        event_filter = "store_id = ? AND is_staff = 0"
        event_params = [store_id]
        
        if start_ts:
            event_filter += " AND timestamp >= ?"
            event_params.append(start_ts)
        if end_ts:
            event_filter += " AND timestamp <= ?"
            event_params.append(end_ts)
            
        # Get total unique customer sessions in the store in the window to compute data_confidence
        sessions_query = f"SELECT count(DISTINCT visitor_id) FROM events WHERE {event_filter}"
        total_sessions = conn.execute(sessions_query, event_params).fetchone()[0] or 0
        confidence = "LOW" if total_sessions < 20 else "NORMAL"
        
        # Query metrics per zone
        zone_data = {}
        for zone_id, zone_meta in layout_zones.items():
            if zone_id == "ENTRY_THRESHOLD":
                continue  # skip threshold
                
            # Count unique visitors who entered or dwelled in this zone
            visit_query = f"""
                SELECT count(DISTINCT visitor_id) FROM events 
                WHERE {event_filter} AND zone_id = ?
            """
            visits = conn.execute(visit_query, event_params + [zone_id]).fetchone()[0] or 0
            
            # Avg dwell in zone
            dwell_query = f"""
                SELECT avg(dwell_ms) FROM events 
                WHERE {event_filter} AND zone_id = ?
            """
            avg_dwell = conn.execute(dwell_query, event_params + [zone_id]).fetchone()[0]
            avg_dwell = round(avg_dwell, 2) if avg_dwell is not None else 0.0
            
            zone_data[zone_id] = {
                "zone_id": zone_id,
                "name": zone_meta.get("name", zone_id),
                "visit_count": visits,
                "avg_dwell_ms": avg_dwell,
                "score": 0.0,
                "data_confidence": confidence
            }
            
        # Normalize scores from 0 to 100
        max_visits = max([z["visit_count"] for z in zone_data.values()]) if zone_data else 0
        max_dwell = max([z["avg_dwell_ms"] for z in zone_data.values()]) if zone_data else 0.0
        
        for zone_id, z in zone_data.items():
            norm_visits = (z["visit_count"] / max_visits) if max_visits > 0 else 0.0
            norm_dwell = (z["avg_dwell_ms"] / max_dwell) if max_dwell > 0.0 else 0.0
            
            # Simple weighted average score (50% frequency, 50% dwell)
            raw_score = 0.5 * norm_visits + 0.5 * norm_dwell
            z["score"] = round(raw_score * 100.0, 2)
            
        return {
            "store_id": store_id,
            "window_start": start_ts,
            "window_end": end_ts,
            "total_sessions": total_sessions,
            "zones": list(zone_data.values())
        }
    finally:
        conn.close()

