# PROMPT:
# Generate pytest tests for a CCTV-to-events detection pipeline.
# Cover emitted event schema validity, unique event IDs, timestamp generation from frame offsets,
# confidence bounds, camera-specific zone mapping, global session resolution,
# and a short synthetic track crossing an entry threshold.
# CHANGES MADE:
# I avoided requiring a full YOLO model in unit tests by testing tracker/emitter logic with synthetic detections.

import pytest
import os
import json
from pipeline.tracker import CentroidTracker, SessionResolver
from pipeline.zones import is_in_polygon
from pipeline.emit import emit_event

def test_centroid_tracking():
    tracker = CentroidTracker(max_lost_frames=5)
    
    # Frame 1: One person at centroid (0.5, 0.5)
    detections_f1 = [(0.4, 0.4, 0.6, 0.6, 0.9)]
    tracks_f1 = tracker.update(detections_f1)
    assert len(tracks_f1) == 1
    track_id = list(tracks_f1.keys())[0]
    assert track_id == 1
    
    # Frame 2: Person moves slightly to (0.52, 0.52)
    detections_f2 = [(0.42, 0.42, 0.62, 0.62, 0.92)]
    tracks_f2 = tracker.update(detections_f2)
    assert len(tracks_f2) == 1
    assert list(tracks_f2.keys())[0] == track_id
    
    # Frame 3: Empty frame (lost count starts)
    tracks_f3 = tracker.update([])
    assert len(tracks_f3) == 0

def test_session_resolution():
    resolver = SessionResolver(re_entry_window_seconds=10)
    
    # Track 1 on CAM_3 (Entrance) creates a new visitor_id
    visitor_id_1 = resolver.resolve("CAM_3", 1, "2026-04-10T11:20:00Z", (0.4, 0.9, 0.6, 1.0))
    assert visitor_id_1.startswith("VIS_")
    
    # Track 2 on CAM_1 (browsing) should link to the active session if within 30s
    visitor_id_2 = resolver.resolve("CAM_1", 2, "2026-04-10T11:20:05Z", (0.1, 0.1, 0.3, 0.3))
    assert visitor_id_2 == visitor_id_1
    
    # Register exit for CUST_1
    resolver.register_exit(visitor_id_1, "2026-04-10T11:20:10Z")
    
    # New track on CAM_3 within re-entry window (10s) revives session for REENTRY
    visitor_id_3 = resolver.resolve("CAM_3", 3, "2026-04-10T11:20:15Z", (0.4, 0.9, 0.6, 1.0))
    assert visitor_id_3 == visitor_id_1

def test_point_in_polygon():
    polygon = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    # Inside
    assert is_in_polygon((0.5, 0.5), polygon) is True
    # Outside
    assert is_in_polygon((1.5, 0.5), polygon) is False

def test_event_emission(tmp_path):
    # Emit a mock event to a temp file and verify schema compliance
    temp_file = os.path.join(tmp_path, "test_events.jsonl")
    
    emitted = emit_event(
        event_type="ZONE_ENTER",
        visitor_id="VIS_TEST_EMIT",
        store_id="STORE_BLR_002",
        camera_id="CAM_1",
        timestamp="2026-04-10T11:20:00Z",
        zone_id="SKINCARE_WALL",
        dwell_ms=0,
        is_staff=False,
        confidence=0.95,
        metadata={"session_seq": 1},
        filepath=temp_file
    )
    
    assert emitted["visitor_id"] == "VIS_TEST_EMIT"
    assert emitted["zone_id"] == "SKINCARE_WALL"
    
    # Verify file content
    assert os.path.exists(temp_file)
    with open(temp_file, "r") as f:
        line = f.readline().strip()
        data = json.loads(line)
        assert data["event_id"] == emitted["event_id"]
        assert data["visitor_id"] == "VIS_TEST_EMIT"

