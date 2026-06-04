# PROMPT:
# test 10 rules. check uuid, uniq, store id, cam id, types, time format, zones, dwell, conf, and sequence
# CHANGES MADE:
# validated local sample events jsonl against rules


import json
import os
import re
import uuid
from datetime import datetime

EVENTS_PATH = os.path.join(os.path.dirname(__file__), "../data/sample_events.jsonl")

def load_layout(store_id: str = "STORE_BLR_002"):
    tests_dir = os.path.dirname(__file__)
    layout_path = os.path.join(tests_dir, "../app/layouts", f"{store_id}.json")
    if not os.path.exists(layout_path):
        layout_path = os.path.join(tests_dir, "../app/store_layout.json")
    with open(layout_path, "r") as f:
        return json.load(f)

def load_events():
    events = []
    if not os.path.exists(EVENTS_PATH):
        return events
    with open(EVENTS_PATH, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events

# Assertions tests

def test_1_event_id_is_valid_uuid():
    events = load_events()
    assert len(events) > 0, "No events loaded for assertion"
    for e in events:
        eid = e.get("event_id")
        assert eid is not None, "Missing event_id"
        # Validate UUID structure
        try:
            val = uuid.UUID(eid, version=4)
            assert str(val) == eid, f"event_id {eid} is not a normalized UUID v4"
        except ValueError:
            assert False, f"event_id {eid} is not a valid UUID v4"

def test_2_event_id_uniqueness():
    events = load_events()
    assert len(events) > 0, "No events loaded for assertion"
    seen_ids = set()
    for e in events:
        eid = e.get("event_id")
        assert eid not in seen_ids, f"Duplicate event_id detected: {eid}"
        seen_ids.add(eid)

def test_3_store_id_validity():
    events = load_events()
    if not events:
        return
    store_id = events[0].get("store_id", "STORE_BLR_002")
    layout = load_layout(store_id)
    valid_store_id = layout.get("store_id")
    for e in events:
        assert e.get("store_id") == valid_store_id, f"Invalid store_id: {e.get('store_id')}"

def test_4_camera_id_validity():
    events = load_events()
    if not events:
        return
    store_id = events[0].get("store_id", "STORE_BLR_002")
    layout = load_layout(store_id)
    valid_camera_ids = set(layout.get("cameras", {}).keys())
    for e in events:
        cam_id = e.get("camera_id")
        assert cam_id in valid_camera_ids, f"Invalid camera_id: {cam_id}"

def test_5_event_type_validity():
    valid_types = {
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
        "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY"
    }
    events = load_events()
    for e in events:
        etype = e.get("event_type")
        assert etype in valid_types, f"Invalid event_type: {etype}"

def test_6_timestamp_format_and_ordering():
    events = load_events()
    # ISO-8601 regex pattern
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
    
    session_times = {}  # visitor_id -> list of datetimes
    for e in events:
        ts_str = e.get("timestamp")
        assert ts_str is not None, "Missing timestamp"
        assert iso_pattern.match(ts_str), f"Timestamp {ts_str} does not match ISO-8601"
        
        # Parse for ordering validation
        # Clean 'Z' for easy datetime parsing
        clean_ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        
        visitor_id = e.get("visitor_id")
        if visitor_id not in session_times:
            session_times[visitor_id] = []
        session_times[visitor_id].append(dt)
        
    for visitor_id, times in session_times.items():
        # Check that within each session, times are monotonically increasing
        for i in range(1, len(times)):
            assert times[i] >= times[i-1], f"Timestamps out of order for session {visitor_id}: {times[i]} < {times[i-1]}"

def test_7_zone_id_rules():
    events = load_events()
    if not events:
        return
    store_id = events[0].get("store_id", "STORE_BLR_002")
    layout = load_layout(store_id)
    valid_zone_ids = set(layout.get("zones", {}).keys())
    
    for e in events:
        etype = e.get("event_type")
        zone_id = e.get("zone_id")
        
        if etype in {"ENTRY", "EXIT", "REENTRY"}:
            assert zone_id is None, f"zone_id must be null for {etype} event"
        else:
            assert zone_id is not None, f"zone_id cannot be null for {etype} event"
            assert zone_id in valid_zone_ids, f"Invalid zone_id {zone_id} for event {etype}"

def test_8_dwell_time_non_negative():
    events = load_events()
    for e in events:
        dwell = e.get("dwell_ms")
        if dwell is not None:
            assert isinstance(dwell, int), "dwell_ms must be an integer"
            assert dwell >= 0, f"dwell_ms must be non-negative, got: {dwell}"

def test_9_confidence_bounds():
    events = load_events()
    for e in events:
        conf = e.get("confidence")
        assert conf is not None, "Missing confidence score"
        assert isinstance(conf, (int, float)), "confidence must be a number"
        assert 0.0 <= conf <= 1.0, f"confidence must be between 0.0 and 1.0, got: {conf}"

def test_10_session_sequence_incrementing():
    events = load_events()
    visitor_sessions = {} # visitor_id -> list of session_seq values
    
    for e in events:
        visitor_id = e.get("visitor_id")
        metadata = e.get("metadata", {})
        assert metadata is not None, "Missing metadata object"
        seq = metadata.get("session_seq")
        assert seq is not None, "Missing session_seq in metadata"
        assert isinstance(seq, int), "session_seq must be an integer"
        
        if visitor_id not in visitor_sessions:
            visitor_sessions[visitor_id] = []
        visitor_sessions[visitor_id].append(seq)
        
    for visitor_id, seqs in visitor_sessions.items():
        # Session sequence must start at 1 or higher (usually 1)
        assert seqs[0] >= 1, f"Session sequence starts at invalid value: {seqs[0]}"
        # Ensure it increases monotonically (no steps backward)
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i-1], f"Session sequence did not increment for {visitor_id}: {seqs[i]} <= {seqs[i-1]}"

if __name__ == "__main__":
    import pytest
    print("Running assertion tests...")
    pytest.main([__file__])
