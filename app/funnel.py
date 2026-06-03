from datetime import datetime, timezone
from typing import Optional
from app.database import get_db_connection
from app.metrics import get_time_range, calculate_conversions

def get_store_funnel(store_id: str, start: Optional[str] = None, end: Optional[str] = None, window: Optional[str] = None) -> dict:
    conn = get_db_connection()
    try:
        start_ts, end_ts = get_time_range(conn, store_id, start, end, window)
        
        # Base filter
        event_filter = "store_id = ? AND is_staff = 0"
        event_params = [store_id]
        
        if start_ts:
            event_filter += " AND timestamp >= ?"
            event_params.append(start_ts)
        if end_ts:
            event_filter += " AND timestamp <= ?"
            event_params.append(end_ts)
            
        # Stage 1: Entry
        # All unique non-staff visitors active in the store in the window
        visitors_query = f"SELECT DISTINCT visitor_id FROM events WHERE {event_filter}"
        visitors = [r["visitor_id"] for r in conn.execute(visitors_query, event_params).fetchall()]
        entry_count = len(visitors)
        
        # Stage 2: Zone Visit
        # Visitors that entered/dwelled in a product or service zone
        # Exclude ENTRY_THRESHOLD and BILLING_COUNTER
        zone_visit_query = f"""
            SELECT DISTINCT visitor_id FROM events 
            WHERE {event_filter} 
              AND zone_id IS NOT NULL 
              AND zone_id NOT IN ('ENTRY_THRESHOLD', 'BILLING_COUNTER')
        """
        visit_visitors = [r["visitor_id"] for r in conn.execute(zone_visit_query, event_params).fetchall()]
        visit_count = len(visit_visitors)
        
        # Stage 3: Billing Queue
        # Visitors present at the billing counter
        billing_query = f"""
            SELECT DISTINCT visitor_id FROM events 
            WHERE {event_filter} AND zone_id = 'BILLING_COUNTER'
        """
        billing_visitors = [r["visitor_id"] for r in conn.execute(billing_query, event_params).fetchall()]
        billing_count = len(billing_visitors)
        
        # Stage 4: Purchase (Conversions)
        # Billing visitors that convert based on POS transactions using standard pairing rules
        purchase_count = 0
        if billing_count > 0:
            converted_billing = calculate_conversions(conn, store_id, billing_visitors, start_ts, end_ts)
            purchase_count = len(converted_billing)
            
        # Calculate percentages relative to Entry stage
        entry_pct = 100.0 if entry_count > 0 else 0.0
        visit_pct = round((visit_count / entry_count) * 100.0, 2) if entry_count > 0 else 0.0
        billing_pct = round((billing_count / entry_count) * 100.0, 2) if entry_count > 0 else 0.0
        purchase_pct = round((purchase_count / entry_count) * 100.0, 2) if entry_count > 0 else 0.0
        
        return {
            "store_id": store_id,
            "window_start": start_ts,
            "window_end": end_ts,
            "stages": [
                {"stage": "1. Entry", "count": entry_count, "percentage": entry_pct},
                {"stage": "2. Zone Visit", "count": visit_count, "percentage": visit_pct},
                {"stage": "3. Billing Queue", "count": billing_count, "percentage": billing_pct},
                {"stage": "4. Purchase", "count": purchase_count, "percentage": purchase_pct}
            ]
        }
    finally:
        conn.close()


