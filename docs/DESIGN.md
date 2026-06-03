# Store Intelligence Architecture

retail cctv analytics system pipeline. processes video, stores events, calculates metrics, serves dashboard.

## System Flow
cctv mp4 clips -> yolov8n detection -> custom tracker -> event emitter -> fastapi -> sqlite -> frontend dashboard.

## Component Spec

### Video Pipeline
* class: person
* resolution: 640px width
* skip rate: process every 5th frame
* output: event log (jsonl)

### API Ingestion (FastAPI)
* endpoint: POST /events/ingest
* validation: pydantic models
* idempotency: sqlite primary key conflict resolution

### Persistence (SQLite)
* tables: events, transactions
* write mode: WAL mode enabled
* access: concurrent read capability

### Analytics Engine
* metrics: unique visitors, conversion rate, dwell times, queue depth, anomalies
* correlation: billing presence to POS transaction timestamps
