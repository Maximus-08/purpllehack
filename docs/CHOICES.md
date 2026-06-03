# Engineering Choices and Decisions

Technical decisions and trade-offs made during system design.

## 1. Detection Model and Tracking Choice

### Options Considered
1. OpenCV HOG / Background Subtraction.
2. YOLOv8n detector with custom Centroid/IoU tracking and Session Resolver.
3. YOLOv8n with DeepSORT / visual Re-ID.

### What AI Suggested
YOLOv8n with DeepSORT.

### Final Choice
YOLOv8n with custom Centroid/IoU tracking and global Session Resolver.

### Rationale
Centroid tracking is fast and lightweight on CPU inside Docker. DeepSORT is too slow. Session resolver groups camera tracks using time bounds.

### Known Limitations
Lacks visual re-identification. Tracker struggles with occlusions and overlapping customer trajectories.

---

## 2. Event Schema Design Rationale

### Options Considered
1. Nested hierarchical session payloads.
2. Flat event streaming format.

### What AI Suggested
Nested session schema.

### Final Choice
Flat event streaming schema.

### Rationale
Flat format simplifies ingestion logic. Simplifies Pydantic validations. Session grouping is offloaded to SQL queries.

### Known Limitations
Increases payload size due to redundant visitor and store properties in every event.

---

## 3. Storage and Database Architecture

### Options Considered
1. PostgreSQL container.
2. In-memory data store.
3. SQLite with WAL mode.

### What AI Suggested
PostgreSQL.

### Final Choice
SQLite with Write-Ahead Logging (WAL) enabled.

### Rationale
SQLite has zero setup overhead. WAL mode allows concurrent reads during ingest writes. Connection pool uses 10 second timeout.

### Known Limitations
Single writer lock. Scale to 40 active stores will require a PostgreSQL upgrade.
