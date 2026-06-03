# PROMPT:
# Generate pytest tests for a session-based retail conversion funnel.
# Cover Entry -> Zone Visit -> Billing Queue -> Purchase, re-entry deduplication,
# cross-camera visitor identity, staff exclusion, and drop-off percentage calculation.
# CHANGES MADE:
# I simplified the fixture sessions so every funnel stage can be manually verified.

import pytest
from app.database import get_db_connection

def test_funnel_stages(client):
    # Setup transaction
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO transactions (transaction_id, store_id, timestamp, basket_value_inr, item_count, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("TXN_FUNNEL_1", "STORE_BLR_002", "2026-04-10T11:25:00Z", 1500.0, 3, "{}"))
    conn.commit()
    conn.close()

    # Ingest mock events
    events = [
        # Customer 1 (converts to Purchase: Entry -> Zone Visit -> Billing -> Purchase)
        {
            "event_id": "f001c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_1",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        {
            "event_id": "f001c92b-8a71-46e3-aef0-d4cfeb287e02",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_1",
            "visitor_id": "CUST_1",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:21:00Z",
            "zone_id": "SKINCARE_WALL",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 2}
        },
        {
            "event_id": "f001c92b-8a71-46e3-aef0-d4cfeb287e03",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_5",
            "visitor_id": "CUST_1",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:23:00Z",
            "zone_id": "BILLING_COUNTER",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 3}
        },
        # Customer 2 (reaches Billing: Entry -> Zone Visit -> Billing)
        {
            "event_id": "f002c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_2",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:05Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        {
            "event_id": "f002c92b-8a71-46e3-aef0-d4cfeb287e02",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_2",
            "visitor_id": "CUST_2",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:21:05Z",
            "zone_id": "MAKEUP_WALL",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 2}
        },
        {
            "event_id": "f002c92b-8a71-46e3-aef0-d4cfeb287e03",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_5",
            "visitor_id": "CUST_2",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:23:05Z",
            "zone_id": "BILLING_COUNTER",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 3}
        },
        # Customer 3 (reaches Zone Visit: Entry -> Zone Visit)
        {
            "event_id": "f003c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_3",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:10Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        {
            "event_id": "f003c92b-8a71-46e3-aef0-d4cfeb287e02",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_2",
            "visitor_id": "CUST_3",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:21:10Z",
            "zone_id": "ACCESSORIES",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 2}
        },
        # Customer 4 (reaches Entry: Entry only)
        {
            "event_id": "f004c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_4",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:15Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        # Customer 4 (re-enters later, should not double count)
        {
            "event_id": "f004c92b-8a71-46e3-aef0-d4cfeb287e02",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_4",
            "event_type": "REENTRY",
            "timestamp": "2026-04-10T11:25:15Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 2}
        },
        # Staff 1 (Excluded from all metrics)
        {
            "event_id": "f005c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "STAFF_1",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:20Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": True,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        }
    ]

    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200

    response = client.get("/stores/STORE_BLR_002/funnel")
    assert response.status_code == 200
    res_json = response.json()
    
    stages = res_json["stages"]
    # 4 unique customers: CUST_1, CUST_2, CUST_3, CUST_4
    assert stages[0]["count"] == 4
    assert stages[0]["percentage"] == 100.0
    
    # 3 unique customers visited product zones: CUST_1, CUST_2, CUST_3
    assert stages[1]["count"] == 3
    assert stages[1]["percentage"] == 75.0
    
    # 2 unique customers went to billing: CUST_1, CUST_2
    assert stages[2]["count"] == 2
    assert stages[2]["percentage"] == 50.0
    
    # 1 unique customer purchased: CUST_1 (linked to TXN_FUNNEL_1 within 5 minutes)
    assert stages[3]["count"] == 1
    assert stages[3]["percentage"] == 25.0

def test_funnel_empty_store(client):
    response = client.get("/stores/STORE_BLR_002/funnel")
    assert response.status_code == 200
    res_json = response.json()
    for stage in res_json["stages"]:
        assert stage["count"] == 0
        assert stage["percentage"] == 0.0

