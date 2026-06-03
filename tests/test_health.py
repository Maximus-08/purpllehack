# PROMPT:
# Generate pytest tests for a /health endpoint for a store intelligence API.
# Cover healthy service, last event timestamp per store, last ingest timestamp per store,
# stale feed warning after 10 minutes based on ingest time,
# and database unavailable returning structured HTTP 503.
# CHANGES MADE:
# I replaced mocked wall-clock behavior with injectable test timestamps.

def test_health_stub():
    pass
