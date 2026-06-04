# PROMPT:
# test health endpoint. verify ok state, timestamps, stale feed check, and db down 503 error
# CHANGES MADE:
# updated test times to check 10 min lag rules


import pytest
from app.database import get_db_connection

def test_health_endpoint_healthy(client):
    # Ingest one valid event
    event = {
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
    client.post("/events/ingest", json=[event])
    
    response = client.get("/health")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "ok"
    assert res_json["database"] == "ok"
    assert res_json["total_events"] == 1
    assert res_json["last_event_timestamp"] == "2026-04-10T11:23:35Z"
    assert res_json["stale_feed"] is False

def test_health_endpoint_stale_feed(client):
    # Ingest one event
    event = {
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
    client.post("/events/ingest", json=[event])
    
    # Manually update created_at to 20 minutes ago
    conn = get_db_connection()
    conn.execute("UPDATE events SET created_at = '2026-04-10T10:00:00Z'")
    conn.commit()
    conn.close()
    
    response = client.get("/health")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["stale_feed"] is True

def test_health_endpoint_database_unavailable(client, monkeypatch):
    import app.main
    # Mock check_db_health to return False
    monkeypatch.setattr(app.main, "check_db_health", lambda: False)
    
    response = client.get("/health")
    assert response.status_code == 503
    res_json = response.json()
    assert res_json["status"] == "error"
    assert res_json["database"] == "unreachable"
