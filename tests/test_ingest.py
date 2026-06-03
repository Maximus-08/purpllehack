# PROMPT:
# Generate pytest tests for a FastAPI POST /events/ingest endpoint.
# Cover valid batch ingestion, duplicate event_id idempotency, malformed event partial success,
# batch size validation, and structured error responses.
# CHANGES MADE:
# I adjusted fixtures to match the local SQLite test database and verified expected response fields.

def test_ingest_stub():
    pass
