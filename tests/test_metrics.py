# PROMPT:
# Generate pytest tests for store metrics from retail CCTV events and POS transactions.
# Cover unique visitors, staff exclusion, zero-purchase stores, average dwell by zone,
# billing queue depth, abandonment rate, historical default windows, and POS multi-line order aggregation.
# CHANGES MADE:
# I replaced generic examples with Brigade Bangalore store IDs and deterministic timestamps.

import pytest
import json
from app.database import get_db_connection

def test_metrics_calculation(client):
    # 1. Insert test transaction
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO transactions (transaction_id, store_id, timestamp, basket_value_inr, item_count, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("TXN_MOCK_1", "STORE_BLR_002", "2026-04-10T16:55:36Z", 500.0, 2, "{}"))
    conn.commit()
    conn.close()

    # 2. Ingest customer events (converts since they go to billing at 16:55:00 UTC)
    events = [
        # Visitor 1 (customer - converts)
        {
            "event_id": "5765c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "VIS_1001",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T16:53:30Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        {
            "event_id": "1042308e-4ed7-4cf9-bfa6-3af5e48dc277",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_5",
            "visitor_id": "VIS_1001",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T16:55:00Z",
            "zone_id": "BILLING_COUNTER",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 7}
        },
        {
            "event_id": "a153419f-5fe8-4df0-afa7-4bf6f59ed388",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_5",
            "visitor_id": "VIS_1001",
            "event_type": "BILLING_QUEUE_JOIN",
            "timestamp": "2026-04-10T16:55:05Z",
            "zone_id": "BILLING_COUNTER",
            "dwell_ms": 5000,
            "is_staff": False,
            "confidence": 0.93,
            "metadata": {"queue_depth": 3, "session_seq": 8}
        },
        # Visitor 2 (staff - excluded from metrics)
        {
            "event_id": "182ab806-2045-4447-bfae-b26d0d346ae5",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "STAFF_2001",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T16:53:31Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": True,
            "confidence": 0.98,
            "metadata": {"session_seq": 1}
        },
        # Visitor 3 (customer - does not convert)
        {
            "event_id": "d48674c2-8c01-4003-bfaa-7e29c8c026b1",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "VIS_1002",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T16:53:40Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.91,
            "metadata": {"session_seq": 1}
        },
        {
            "event_id": "e59785d3-9d12-4114-bfab-8f3ada0137c2",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_2",
            "visitor_id": "VIS_1002",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T16:53:55Z",
            "zone_id": "ACCESSORIES",
            "dwell_ms": 10000,
            "is_staff": False,
            "confidence": 0.88,
            "metadata": {"session_seq": 2}
        }
    ]
    
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    # Check metrics
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.status_code == 200
    res_json = response.json()
    
    # 2 unique customers (VIS_1001, VIS_1002), staff is excluded
    assert res_json["unique_visitors"] == 2
    # 1 converts (VIS_1001), 1 doesn't (VIS_1002). Rate = 1/2 = 50%
    assert res_json["conversion_rate"] == 0.5
    # Dwell in ACCESSORIES
    assert res_json["avg_dwell_ms_by_zone"]["ACCESSORIES"] == 10000.0
    # Queue depth
    assert res_json["current_queue_depth"] == 3

def test_metrics_empty_store(client):
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["unique_visitors"] == 0
    assert res_json["conversion_rate"] == 0.0
    assert len(res_json["avg_dwell_ms_by_zone"]) == 0
    assert res_json["current_queue_depth"] == 0
