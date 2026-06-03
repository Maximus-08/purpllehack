# Store Intelligence System

Offline store analytics system that consumes CCTV events, persists data, and processes business metrics. Currently implements Phase 2 of development.

## Setup and Installation

### 1. Requirements
Ensure Python 3.12 and SQLite are installed. Virtualenv is used for isolation.

### 2. Quick Start
Initialize virtualenv and install requirements.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the API
Run the FastAPI development server.

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running Tests

Verify schema validation, ingestion logic, and metric calculations.

### Run unit test suite
```bash
pytest --cov=app --cov-report=term-missing
```

### Run standalone dataset assertions
```bash
python tests/assertions.py
```

## Implemented Features

### Data Layout (Phase 2)
* `data/store_layout.json`: Contains store parameters, camera specs, and normalized polygons.
* `data/sample_events.jsonl`: Simulated customer journeys for testing conversion and re-entry logic.

### Application Underlay
* `app/models.py`: Pydantic validation schemas.
* `app/database.py`: SQLite WAL database tables setup.
* `app/pos.py`: Normalized POS CSV parser grouping orders.
* `app/main.py`: Ingest, health, and store metrics API.
