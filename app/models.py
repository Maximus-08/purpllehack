from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any
import re

EVENT_TYPES = {
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
    "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY"
}

class EventModel(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: str
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"event_type must be one of {EVENT_TYPES}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
        if not iso_pattern.match(v):
            raise ValueError(f"timestamp '{v}' must be a valid ISO-8601 string")
        return v

    @field_validator("dwell_ms")
    @classmethod
    def validate_dwell_ms(cls, v: int) -> int:
        if v < 0:
            raise ValueError("dwell_ms must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_zone_id(self) -> "EventModel":
        etype = self.event_type
        zone = self.zone_id
        if etype in {"ENTRY", "EXIT", "REENTRY"}:
            if zone is not None:
                raise ValueError(f"zone_id must be null for {etype} events")
        else:
            if zone is None or str(zone).strip() == "":
                raise ValueError(f"zone_id is required for {etype} events")
        return self
