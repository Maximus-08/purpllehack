# PROMPT:
# Generate pytest tests for a retail zone heatmap endpoint.
# Cover zone visit frequency, average dwell, 0-100 normalization,
# empty zones, and low data_confidence when fewer than 20 sessions exist.
# CHANGES MADE:
# I aligned zone IDs with the manually encoded store_layout.json file.

import pytest
from app.database import get_db_connection

def test_heatmap_calculation_and_normalization(client):
    # Ingest mock events in different zones
    events = [
        # Customer 1: in SKINCARE_WALL (dwell 10s)
        {
            "event_id": "h001c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_1",
            "visitor_id": "CUST_H1",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": "SKINCARE_WALL",
            "dwell_ms": 10000,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        # Customer 2: in SKINCARE_WALL (dwell 20s)
        {
            "event_id": "h002c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_1",
            "visitor_id": "CUST_H2",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:20:05Z",
            "zone_id": "SKINCARE_WALL",
            "dwell_ms": 20000,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        },
        # Customer 3: in MAKEUP_WALL (dwell 30s)
        {
            "event_id": "h003c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_2",
            "visitor_id": "CUST_H3",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T11:20:10Z",
            "zone_id": "MAKEUP_WALL",
            "dwell_ms": 30000,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        }
    ]
    
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    response = client.get("/stores/STORE_BLR_002/heatmap")
    assert response.status_code == 200
    res_json = response.json()
    
    # 3 unique customer sessions -> confidence should be LOW
    assert res_json["total_sessions"] == 3
    
    # Find skincare wall and makeup wall
    zones_list = res_json["zones"]
    skincare = next(z for z in zones_list if z["zone_id"] == "SKINCARE_WALL")
    makeup = next(z for z in zones_list if z["zone_id"] == "MAKEUP_WALL")
    accessories = next(z for z in zones_list if z["zone_id"] == "ACCESSORIES")
    
    # SKINCARE_WALL: 2 visits, average dwell = (10000 + 20000)/2 = 15000ms
    assert skincare["visit_count"] == 2
    assert skincare["avg_dwell_ms"] == 15000.0
    
    # MAKEUP_WALL: 1 visit, average dwell = 30000ms
    assert makeup["visit_count"] == 1
    assert makeup["avg_dwell_ms"] == 30000.0
    
    # ACCESSORIES: 0 visits, 0.0 avg_dwell
    assert accessories["visit_count"] == 0
    assert accessories["avg_dwell_ms"] == 0.0
    assert accessories["score"] == 0.0
    
    # Data confidence must be LOW because total sessions = 3 < 20
    assert skincare["data_confidence"] == "LOW"
    
    # Check score normalization:
    # Max visits = 2 (skincare)
    # Max average dwell = 30000.0 (makeup)
    # Skincare score: 0.5 * (2/2) + 0.5 * (15000/30000) = 0.5 + 0.25 = 0.75 -> 75.0
    # Makeup score: 0.5 * (1/2) + 0.5 * (30000/30000) = 0.25 + 0.5 = 0.75 -> 75.0
    assert skincare["score"] == 75.0
    assert makeup["score"] == 75.0

def test_heatmap_high_confidence(client):
    # Ingest 20 unique visitor entries to trigger NORMAL data confidence
    events = []
    for i in range(20):
        events.append({
            "event_id": f"h{i:03d}c92b-8a71-46e3-aef0-d4cfeb287e01",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_3",
            "visitor_id": f"CUST_CONF_{i}",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T11:20:00Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.95,
            "metadata": {"session_seq": 1}
        })
        
    response = client.post("/events/ingest", json=events)
    assert response.status_code == 200
    
    response = client.get("/stores/STORE_BLR_002/heatmap")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["total_sessions"] == 20
    for z in res_json["zones"]:
        assert z["data_confidence"] == "NORMAL"

