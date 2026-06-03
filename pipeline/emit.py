import os
import json
import uuid
from typing import Optional, Dict, Any
from app.models import EventModel

def emit_event(
    event_type: str,
    visitor_id: str,
    store_id: str,
    camera_id: str,
    timestamp: str,
    zone_id: Optional[str] = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
    filepath: str = "data/generated_events.jsonl"
) -> dict:
    # 1. Build raw dict
    event_dict = {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": int(dwell_ms),
        "is_staff": bool(is_staff),
        "confidence": float(confidence),
        "metadata": metadata or {}
    }
    
    # 2. Validate using Pydantic
    validated = EventModel(**event_dict)
    
    # Create directory if it doesn't exist
    dir_name = os.path.dirname(filepath)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
        
    # 3. Append to JSONL file
    with open(filepath, "a") as f:
        f.write(json.dumps(validated.dict()) + "\n")
        
    return validated.dict()

