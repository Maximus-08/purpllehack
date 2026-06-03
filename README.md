# Store Intelligence System

Offline retail analytics system that processes store CCTV footage, parses transactional records, and serves real-time performance metrics via a FastAPI service and live web dashboard.

## Setup and Installation

### Quick Start (Local Setup)

Initialize the environment and launch the application in five commands:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m pytest
uvicorn app.main:app --reload
```

---

## Container Execution

Launch the API service inside Docker using Docker Compose:

```bash
docker compose up --build
```

The API service initializes database tables and seeds store transactions from the POS CSV file during startup.

---

## Execution and Replay

### 1. Run CCTV Detection Pipeline
Processes all local CCTV footage clips. Uses YOLOv8n CPU-only person detection. Writes validated visitor tracking events to the JSONL log file:

```bash
bash pipeline/run.sh
```

*Note: Processing runs on CPU. Frame-skipping is enabled to process every fifth frame for resource efficiency.*

### 2. Replay Visitor Events
Simulates live visitor activity by posting batch event payloads to the API. Update metrics live on the dashboard:

```bash
python3 pipeline/replay.py --mode fast
```

*Replay modes supported: `fast`, `demo`, `realtime`.*

---

## Live Dashboard

Open the live operational web interface in your browser:

```text
http://localhost:8000/dashboard/
```

Displays active unique customer visitors, conversion rate, cash counter queue depth, zone engagement heatmap cards, and system anomalies.

---

## Core API Endpoints

### 1. Events Ingestion
- `POST /events/ingest`: Ingests a batch of visitor events (up to 500). Enforces idempotency via event IDs. Returns partial success reports.

### 2. Store Analytics
- `GET /stores/{store_id}/metrics`: Returns unique visitors, conversion rate, queue depth, and zone dwells.
- `GET /stores/{store_id}/funnel`: Returns session-based retail funnel conversion stages.
- `GET /stores/{store_id}/heatmap`: Returns normalized zone engagement metrics.
- `GET /stores/{store_id}/anomalies`: Identifies active store operation issues.

### 3. Service Status
- `GET /health`: Returns service, SQLite database WAL mode status, and ingestion warnings.

---

## Running Verification Tests

Run the complete test suite:

```bash
pytest --cov=app --cov-report=term-missing
```

Run structural and semantic dataset assertions check:

```bash
pytest tests/assertions.py
```
