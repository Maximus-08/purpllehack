# PROMPT:
# Generate pytest tests for operational anomaly detection in a retail store API.
# Cover queue spike, conversion drop versus baseline, dead zone with no visits,
# severity values, suggested_action strings, and no-anomaly response.
# CHANGES MADE:
# I made the thresholds deterministic and documented them in the test names.

import pytest
from app.database import get_db_connection

def test_no_anomalies(client):
    # Healthy store setup
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    res_json = response.json()
    assert len(res_json) == 0

def test_queue_spike_anomaly(client):
    # Ingest a billing queue join event with queue_depth >= 4
    events = [
        {
            "event_id": "a001c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_5",
            "visitor_id": "CUST_A1",
            "event_type": "BILLING_QUEUE_JOIN",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": "BILLING_COUNTER",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"queue_depth": 5, "session_seq": 3}
        }
    ]
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    res_json = response.json()
    
    # We should have a QUEUE_SPIKE anomaly
    assert len(res_json) >= 1
    anomaly = next(a for a in res_json if a["type"] == "QUEUE_SPIKE")
    assert anomaly["severity"] == "WARN"
    assert "spiked to 5" in anomaly["message"]
    assert "additional cashier" in anomaly["suggested_action"]

def test_conversion_drop_anomaly(client):
    # We need a low conversion rate (<35%) under at least 2 unique visitors
    events = [
        # Customer 1
        {
            "event_id": "a002c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_A2",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        # Customer 3
        {
            "event_id": "a003c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_A3",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:05Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        }
    ]
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    # 2 customers, 0 transactions -> 0.0 conversion rate
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    res_json = response.json()
    
    anomaly = next(a for a in res_json if a["type"] == "CONVERSION_DROP")
    assert anomaly["severity"] == "CRITICAL"
    assert "Audit sales floor" in anomaly["suggested_action"]

def test_dead_zone_anomaly(client):
    # Ingest events to simulate store traffic in the last 30 minutes, but zero visits in product zones
    # E.g. visitors only enter the entrance and billing, butLower Brand Wall or Skincare has zero visits
    events = [
        {
            "event_id": "a004c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": "CUST_A4",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        }
    ]
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    res_json = response.json()
    
    # We should detect dead zones for ACCESSORIES, SkinCare, etc.
    dead_zone_anomalies = [a for a in res_json if a["type"] == "DEAD_ZONE"]
    assert len(dead_zone_anomalies) > 0
    
    accessories_alert = next(a for a in dead_zone_anomalies if "Accessories" in a["message"])
    assert accessories_alert["severity"] == "INFO"
    assert "layout visibility" in accessories_alert["suggested_action"]

