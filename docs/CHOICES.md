# Engineering Choices and Decisions

Technical decisions and trade-offs made during system design.

## 1. Detection Model and Tracking Choice

### Options Considered
1. OpenCV HOG / Background Subtraction. This is computationally cheap but inaccurate.
2. YOLOv8n detector with custom Centroid/IoU tracking and global Session Resolver.
3. YOLOv8n with DeepSORT / visual Re-ID.
4. Manual or purely synthetic event generation.

### What AI Suggested
YOLOv8n with DeepSORT.

### Final Choice
YOLOv8n with custom Centroid/IoU tracking and global Session Resolver.

### Rationale
Centroid tracking is fast and lightweight on CPU inside Docker. DeepSORT is too slow for CPU execution, causing frame bottlenecks. The custom session resolver groups camera tracks using time bounds and entry history. We process every fifth frame to reduce CPU utilization. Detections coordinates are normalized to support resolution-independent polygon mapping. Global session resolving links camera-local tracks by temporal proximity and spatial overlap within a thirty second window.

### Known Limitations
Lacks visual re-identification. The tracker struggles with occlusions and overlapping customer trajectories.

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
The flat format simplifies ingestion logic. It simplifies Pydantic validations. Session grouping is offloaded to SQL queries. Flat structures are easier to store in SQLite columns. We validate schema rules using Pydantic, including confidence score constraints between 0.0 and 1.0, non-negative dwells, and event type enums.

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
SQLite has zero setup overhead. WAL mode allows concurrent reads during ingest writes. Connection pool uses a ten second timeout. This supports concurrent dashboard queries during replay writes. In-memory storage was rejected because it loses data on restart and prevents idempotency testing. WAL mode is enabled via PRAGMA journal_mode=WAL.

### Known Limitations
SQLite has a single writer lock. Scale to forty active stores will require a PostgreSQL upgrade.
