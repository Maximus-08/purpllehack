# Store Intelligence System: Architecture (Draft)

*Note: This is an active design document for Phase 1. Details will be updated as the implementation proceeds.*

## 1. Overview
The system is designed to take CCTV footage from a Purplle retail store, run it through a person detection and tracking pipeline, convert observations into structured events, ingest them via a FastAPI backend, and display real-time analytics on a sleek dashboard.

```
CCTV Clips → YOLOv8n Detection → Event Stream → FastAPI + SQLite → Dashboard
```

## 2. High-Level Architecture (Planned)

### 2.1 Component Data Flow
1. **CCTV Footage (Local MP4s)**: Raw inputs to the video processing pipeline.
2. **Detection & Tracking Pipeline**: Uses YOLOv8n for CPU-based person detection and tracking, emitting zone entry/exit events.
3. **Ingestion API (FastAPI)**: Receives event streams in batches, validating and saving them.
4. **Database (SQLite)**: Simple, transactional storage of events and correlated POS sales data.
5. **Dashboard**: A minimal frontend polling metrics from the API to show conversion, heatmap, and queue analytics.

## 3. Implementation Plan Status
- [x] Phase 1: Scaffolding and folder structures.
- [ ] Phase 2: Store layout definition and polygon mapping.
- [ ] Phase 3: POS data parsing.
- [ ] Phase 4: Person detection and tracking.
- [ ] Phase 5: Event emission and API endpoints.
- [ ] Phase 6: Dashboard visual updates.

*Additional sections (SQLite tables, specific metric math, and final AI-assisted decisions) will be documented as they are built.*
