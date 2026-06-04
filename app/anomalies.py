from datetime import datetime, timezone, timedelta
import json
import os
from typing import List
from app.database import get_db_connection
from app.metrics import get_store_metrics

LAYOUT_PATH = os.path.join(os.path.dirname(__file__), "store_layout.json")

def load_product_zones() -> dict:
    if not os.path.exists(LAYOUT_PATH):
        return {}
    with open(LAYOUT_PATH, "r") as f:
        data = json.load(f)
        zones = data.get("zones", {})
        # Filter product or service zones
        return {zid: z for zid, z in zones.items() if z.get("zone_type") in ("product", "service")}

def get_store_anomalies(store_id: str) -> List[dict]:
    conn = get_db_connection()
    try:
        # Determine the "current time" based on the latest event timestamp in DB
        row = conn.execute("SELECT max(timestamp) FROM events WHERE store_id = ?", (store_id,)).fetchone()
        max_ts_str = row[0] if row and row[0] is not None else None
        
        if max_ts_str:
            current_dt = datetime.fromisoformat(max_ts_str.replace("Z", "+00:00"))
        else:
            current_dt = datetime.now(timezone.utc)
            
        detected_at_str = current_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        anomalies = []
        
        # 1. Queue Spike Check
        # Check queue depth in the last 5 minutes
        start_5m = (current_dt - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        queue_query = """
            SELECT max(CAST(json_extract(metadata_json, '$.queue_depth') AS INTEGER)) as max_q
            FROM events 
            WHERE store_id = ? AND event_type = 'BILLING_QUEUE_JOIN' AND is_staff = 0
              AND timestamp >= ? AND timestamp <= ?
        """
        max_q = conn.execute(queue_query, [store_id, start_5m, detected_at_str]).fetchone()["max_q"]
        if max_q is not None and max_q >= 4:
            anomalies.append({
                "type": "QUEUE_SPIKE",
                "severity": "WARN",
                "message": f"Billing queue depth has spiked to {max_q}.",
                "suggested_action": "Deploy additional cashier to billing counter.",
                "detected_at": detected_at_str,
                "metadata": {"queue_depth": max_q}
            })
            
        # 2. Conversion Drop Check
        # Run metrics for the latest business day
        metrics = get_store_metrics(store_id, window="latest_day")
        unique_visitors = metrics.get("unique_visitors", 0)
        conversion_rate = metrics.get("conversion_rate", 0.0)
        
        # Threshold: if conversion drops below 35% (30% drop below a 50% baseline target)
        if unique_visitors >= 2 and conversion_rate < 0.35:
            anomalies.append({
                "type": "CONVERSION_DROP",
                "severity": "CRITICAL",
                "message": f"Conversion rate is currently at {conversion_rate:.1%}, which is more than 30% below target baseline of 50.0%.",
                "suggested_action": "Audit sales floor assistance or product placement.",
                "detected_at": detected_at_str,
                "metadata": {"conversion_rate": conversion_rate, "unique_visitors": unique_visitors}
            })
            
        # 3. Dead Zone Check
        # Check if there is any traffic in the store in the last 30 minutes
        start_30m = (current_dt - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        traffic_query = """
            SELECT count(*) FROM events 
            WHERE store_id = ? AND is_staff = 0 AND timestamp >= ? AND timestamp <= ?
        """
        recent_traffic = conn.execute(traffic_query, [store_id, start_30m, detected_at_str]).fetchone()[0] or 0
        
        if recent_traffic > 0:
            product_zones = load_product_zones()
            for zone_id, zone_meta in product_zones.items():
                zone_visits_query = """
                    SELECT count(*) FROM events 
                    WHERE store_id = ? AND zone_id = ? AND is_staff = 0
                      AND timestamp >= ? AND timestamp <= ?
                """
                zone_visits = conn.execute(zone_visits_query, [store_id, zone_id, start_30m, detected_at_str]).fetchone()[0] or 0
                if zone_visits == 0:
                    anomalies.append({
                        "type": "DEAD_ZONE",
                        "severity": "INFO",
                        "message": f"Zone {zone_meta.get('name', zone_id)} has received zero customer visits in the last 30 minutes.",
                        "suggested_action": "Check product availability or layout visibility in this zone.",
                        "detected_at": detected_at_str,
                        "metadata": {"zone_id": zone_id, "recent_store_traffic_events": recent_traffic}
                    })
                    
        return anomalies
    finally:
        conn.close()

