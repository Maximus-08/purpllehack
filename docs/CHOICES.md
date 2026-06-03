# Engineering Choices (Draft)

*This document outlines the initial engineering options under consideration for the Store Intelligence System. Choices will be finalized and documented during implementation.*

## 1. Detection Model and Tracking Choice (Phase 4)
We need to detect and track people on CPU-only containers while keeping tracking stable and explainable.

### Options Considered
- **Option A**: YOLOv8n + centroid/IoU tracker (Fast, explainable, lightweight).
- **Option B**: OpenCV HOG + Background Subtraction (Very fast, but inaccurate for groups/lighting).
- **Option C**: YOLOv8m + DeepSORT (Higher accuracy, but heavy CPU footprint and hard to package).

*Current Direction*: We are leaning towards Option A (YOLOv8n + custom centroid tracking) for its balance of CPU efficiency and clear logic.

---

## 2. Event Schema Design (Phase 5)
How the pipeline reports actions (entry, zone transitions, queue state) to the ingestion server.

### Options Considered
- **Option A**: Flat event stream (emits independent events like `ENTRY`, `ZONE_ENTER` on transitions).
- **Option B**: Session-based JSON (updates a single large session document per visitor).

*Current Direction*: Leaning towards flat event schemas to remain compliant with standard streaming architecture and standard validation patterns.

---

## 3. Database & Storage Architecture (Phase 6)
Persisting events and POS transactions for analytics.

### Options Considered
- **Option A**: SQLite with WAL (Zero-config, embedded, reliable, supports concurrent readers).
- **Option B**: PostgreSQL (Full relational DB, requires a second container/configuration).
- **Option C**: In-Memory structures (Fast, but lacks persistence across container restarts).

*Current Direction*: Leaning towards SQLite to keep container orchestration single-instance and easy for reviewers to boot.
