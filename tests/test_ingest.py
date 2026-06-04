# PROMPT:
# test events ingest endpoint. cover batching, idempotency, partial failures, and bad schema rejects
# CHANGES MADE:
# verified db states and fastapi validation errors


import pytest
from app.database import get_db_connection

def test_valid_batch_ingestion(client):
    event_data = {
        "event_id": "5765c92b-8a71-46e3-aef0-d4cfeb287e01",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_3",
        "visitor_id": "VIS_1001",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T11:23:35Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {"session_seq": 1}
    }
    
    response = client.post("/events/ingest", json=[event_data])
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["accepted"] == 1
    assert res_json["duplicates"] == 0
    assert res_json["rejected"] == 0
    assert len(res_json["errors"]) == 0
    
    # Verify in DB
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_data["event_id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row["visitor_id"] == "VIS_1001"

def test_duplicate_event_id_idempotency(client):
    event_data = {
        "event_id": "24b61d3c-9b82-47f4-bfa1-e5d0fc398e02",
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_1",
        "visitor_id": "VIS_1001",
        "event_type": "ZONE_ENTER",
        "timestamp": "2026-04-10T11:23:45Z",
        "zone_id": "SKINCARE_WALL",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.92,
        "metadata": {"sku_zone": "MOISTURISER", "session_seq": 2}
    }
    
    # First ingest
    response = client.post("/events/ingest", json=[event_data])
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    
    # Second ingest of duplicate event_id
    response = client.post("/events/ingest", json=[event_data])
    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["duplicates"] == 1

def test_malformed_event_partial_success(client):
    # One valid, one invalid (missing store_id), one invalid (negative dwell_ms)
    events = [
        {
            "event_id": "c9078f4a-0a93-48f5-bfa2-f6e1a04a9f03",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_1",
            "visitor_id": "VIS_1001",
            "event_type": "ZONE_DWELL",
            "timestamp": "2026-04-10T11:24:15Z",
            "zone_id": "SKINCARE_WALL",
            "dwell_ms": 30000,
            "is_staff": False,
            "confidence": 0.94,
            "metadata": {"session_seq": 3}
        },
        {
            "event_id": "f8190c5b-1ba4-49f6-afa3-07f2b15baf04",
            # missing store_id
            "camera_id": "CAM_1",
            "visitor_id": "VIS_1001",
            "event_type": "ZONE_EXIT",
            "timestamp": "2026-04-10T11:24:20Z",
            "zone_id": "SKINCARE_WALL",
            "dwell_ms": 35000,
            "is_staff": False,
            "confidence": 0.93,
            "metadata": {"session_seq": 4}
        },
        {
            "event_id": "d6201e6c-2cb5-4af7-bfa4-18f3c26cb055",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_2",
            "visitor_id": "VIS_1001",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:24:30Z",
            "zone_id": "MAKEUP_WALL",
            "dwell_ms": -100, # invalid negative dwell
            "is_staff": False,
            "confidence": 0.89,
            "metadata": {"session_seq": 5}
        }
    ]
    
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["accepted"] == 1
    assert res_json["rejected"] == 2
    assert len(res_json["errors"]) == 2
    assert res_json["errors"][0]["index"] == 1
    assert res_json["errors"][1]["index"] == 2

def test_batch_size_validation(client):
    # Exceed limit of 500 events
    large_batch = [{"event_id": str(i)} for i in range(501)]
    response = client.post("/events/ingest", json=large_batch)
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"]
