# Purplle Store Intelligence Implementation Plan

## 1. Objective

Build a working, containerized Store Intelligence system for the Purplle hackathon dataset in this repository. The system should start from the provided CCTV clips, emit structured visitor behavior events, ingest those events into an API, compute live retail metrics, and expose a simple dashboard.

This plan optimizes for a score-oriented MVP:

- CPU-only Docker execution.
- Real, lightweight computer vision instead of hardcoded outputs.
- Strong API correctness and test coverage.
- Clear documentation of design choices and AI-assisted reasoning.
- Simple live web dashboard for bonus points.

## 2. Local Dataset Facts

The challenge statement describes a larger generic dataset, but this repository currently contains a smaller, concrete dataset:

- Store: `ST1008`, `Brigade_Bangalore`, Bangalore.
- CCTV: 5 MP4 clips under `CCTV Footage/CCTV Footage/`.
- Video shape: 1080p clips, roughly 2 to 2.5 minutes each.
- POS data: `Brigade_Bangalore_10_April_26.csv`.
- POS rows: 101 line items.
- Unique orders: 24, grouped by `order_id` / `invoice_number`.
- POS time range: `2026-04-10 12:15:05` to `2026-04-10 21:39:55`.
- Store layout: `store_layout.png` and `Brigade Road - Store layout.xlsx`.
- Missing from the generic challenge archive: `store_layout.json`, `sample_events.jsonl`, and `assertions.py`.

Implementation should create compatible local replacements where needed, especially `data/store_layout.json` and generated sample events.

## 3. Recommended Repository Structure

Create this structure:

```text
purplleHack/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── ingestion.py
│   ├── metrics.py
│   ├── funnel.py
│   ├── heatmap.py
│   ├── anomalies.py
│   ├── health.py
│   ├── logging_config.py
│   └── pos.py
├── pipeline/
│   ├── __init__.py
│   ├── detect.py
│   ├── tracker.py
│   ├── zones.py
│   ├── emit.py
│   ├── replay.py
│   └── run.sh
├── dashboard/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── store_layout.json
│   ├── sample_events.jsonl
│   └── generated_events.jsonl
├── tests/
│   ├── test_ingest.py
│   ├── test_metrics.py
│   ├── test_funnel.py
│   ├── test_heatmap.py
│   ├── test_anomalies.py
│   ├── test_health.py
│   └── test_pipeline.py
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── README.md
└── IMPLEMENTATION_PLAN.md
```

## 4. Implementation Phases

### Phase 1: Scaffold And Dependencies

Create the app and pipeline skeleton first, before touching CV logic.

Use Python with:

- `fastapi` and `uvicorn` for the API.
- `pydantic` for event validation.
- `sqlalchemy` or direct `sqlite3` for persistence.
- `pytest`, `pytest-cov`, and `httpx` for tests.
- `opencv-python-headless` for video handling.
- `ultralytics` for YOLOv8n person detection.
- `numpy` for geometry and tracking operations.
- `python-json-logger` or structured logging with the standard library.

Prefer direct `sqlite3` or lightweight SQLAlchemy. SQLite is enough for this challenge and keeps `docker compose up` simple.

### Phase 1.5: Camera Verification

Before assigning camera-to-zone mappings, extract the first frame from each of the 5 clips:

```bash
for i in 1 2 3 4 5; do
  ffmpeg -i "CCTV Footage/CCTV Footage/CAM ${i}.mp4" -frames:v 1 "data/cam${i}_frame0.jpg"
done
```

Visually inspect each frame to confirm which camera covers which area of the store. The current mapping assumptions are:

- `CAM_1`: main floor, skincare and central product shelves.
- `CAM_2`: makeup wall and main browsing area.
- `CAM_3`: entrance and exit threshold.
- `CAM_4`: side room / PMU area.
- `CAM_5`: billing and cash counter.

This must be verified before proceeding. If any mapping is wrong, update `data/store_layout.json` accordingly.

### Phase 2: Store Layout Encoding

Create `data/store_layout.json` manually from `store_layout.png` and the verified camera frames.

Use normalized coordinates from `0.0` to `1.0` so polygons are resolution-independent. Include:

- Store metadata:
  - `store_id`: `STORE_BLR_002`
  - `source_store_id`: `ST1008`
  - `store_name`: `Brigade_Bangalore`
  - `city`: `Bangalore`
  - `timezone`: `Asia/Kolkata`
  - `business_date`: `2026-04-10`
  - `open_hours_local`: documented opening and closing window, even if approximate
- Camera IDs:
  - `CAM_1`: main floor, skincare and central product shelves.
  - `CAM_2`: makeup wall and main browsing area.
  - `CAM_3`: entrance and exit threshold.
  - `CAM_4`: side room / PMU area.
  - `CAM_5`: billing and cash counter.
- Camera clip metadata for each camera:
  - `file_path`
  - `fps`
  - `duration_seconds`
  - `clip_start_at_local`
  - `clip_start_at_utc`
  - `timestamp_source`: `observed`, `inferred`, or `demo_assumption`
- Zone IDs:
  - `ENTRY_THRESHOLD`
  - `BILLING_COUNTER`
  - `PMU`
  - `MAKEUP_WALL`
  - `SKINCARE_WALL`
  - `CENTER_MAKEUP_UNIT`
  - `LOWER_BRAND_WALL`
  - `ACCESSORIES`

Each zone should include:

- `zone_id`
- `name`
- `zone_type`: one of `entry`, `billing`, `product`, `service`
- `camera_ids`
- `floorplan_polygon_norm` for dashboard display on the store layout
- `camera_polygons`, keyed by camera ID, for frame-space detection:
  ```json
  {
    "CAM_1": [[0.10, 0.20], [0.45, 0.20], [0.45, 0.80], [0.10, 0.80]],
    "CAM_2": [[0.05, 0.15], [0.35, 0.15], [0.35, 0.70], [0.05, 0.70]]
  }
  ```
- optional `sku_zone`

Do not use one shared `polygon_norm` for all camera views. Each CCTV angle has its own perspective, so analytics must use `camera_polygons`; the dashboard may use `floorplan_polygon_norm`.

Keep the polygons approximate. The scoring values explainability and useful behavior more than centimeter-perfect geometry, but the assumptions must be documented in `DESIGN.md`.

#### Timestamp Alignment

The POS file is historical (`2026-04-10`), while reviewers may run the app on a later date. Define a clear timestamp strategy before generating events:

- Events should be emitted in UTC ISO-8601.
- Frame timestamps should be computed as `clip_start_at_utc + frame_index / fps`.
- If real clip start times are unknown, choose a documented inferred start time on `2026-04-10` that overlaps the POS day and mark `timestamp_source: demo_assumption`.
- The API must support explicit metric windows via query params so historical events can be evaluated even when the current wall-clock date is different.

### Phase 2.5: Generate Missing Dataset Files

The challenge describes `store_layout.json`, `sample_events.jsonl`, and `assertions.py` but these are not included in our local dataset. Create compatible local replacements:

- `data/store_layout.json`: from Phase 2 above.
- `data/sample_events.jsonl`: preferably generate 200 sample events after the pipeline runs on at least one clip. Synthetic examples are allowed only as clearly named test fixtures, not as the primary demo output.
- `data/generated_events.jsonl`: must be produced by the real detection pipeline from at least one CCTV clip. This file can be replayed for demos, but should not look hand-authored or invariant across inputs.
- `tests/assertions.py`: write 10 assertion tests that validate API correctness (schema compliance, idempotency, funnel accuracy, etc.).

### Phase 3: POS Normalization

Implement `app/pos.py` to load and normalize `Brigade_Bangalore_10_April_26.csv`.

Rules:

- Group by `order_id` and `invoice_number`.
- Keep one transaction per order.
- Treat POS rows as line items, not purchases. Never count CSV rows directly as transactions.
- Use only `invoice_type=sales` rows for purchase metrics. If return rows exist, either exclude them from conversion or model them separately and document the choice.
- Ignore rows with a populated `return_id` for the first-pass conversion metric unless the row clearly represents a valid sale.
- Compute:
  - `transaction_id`
  - `store_id`
  - `source_store_id`
  - `timestamp`
  - `basket_value_inr`
  - `item_count`
  - `line_count`
- Build `transaction_id` from `invoice_number` when present, otherwise `order_id`.
- Compute `basket_value_inr` by summing line-level `NMV` for the order. If `NMV` is missing or unparsable for a line, fall back to `total_amount`, then `GMV`, then `0.0`.
- Compute `item_count` as the sum of `qty`; compute `line_count` as the number of rows in the grouped order.
- Parse `order_date` + `order_time` as `Asia/Kolkata`.
- Store timestamps consistently in ISO-8601 UTC internally, and document the local-to-UTC conversion in `DESIGN.md`.
- Add tests for multi-line orders so one purchase with multiple SKUs still counts as one conversion.

### Phase 4: Detection Pipeline

Implement a real but lightweight pipeline in `pipeline/detect.py`.

Recommended approach:

- Use YOLOv8n person detection on CPU.
- Run detection every N frames, for example every 5th frame, to reduce CPU cost.
- Keep only class `person`.
- Use confidence threshold around `0.25`, but preserve the actual confidence on emitted events.
- Track detections per camera using centroid and IoU matching.
- Resolve camera-local tracks into store-level visitor sessions before emitting business events.
- Maintain track state:
  - `camera_track_id`
  - `camera_id`
  - `visitor_id`
  - last bounding box
  - last centroid
  - active zone
  - first seen timestamp
  - last seen timestamp
  - session sequence number
  - staff heuristic score

Do not make the unit tests depend on YOLO. Test tracker and event emitter with synthetic detections.

#### Global Session Resolver

Do not use camera-local track IDs as final `visitor_id` values. A visitor may appear in `CAM_3` at entry, later in browsing cameras, and then in `CAM_5` at billing. The API funnel and POS conversion logic only work if those observations can share a store-level session identity.

Implement `pipeline/tracker.py` with two layers:

1. Camera tracker:
   - Maintains stable `camera_track_id` values within each camera.
   - Handles short occlusions and frame skips.
   - Emits observations with timestamp, camera, bbox, centroid, optional color histogram, zone candidate, and confidence.
2. Session resolver:
   - Assigns or reuses a global `visitor_id`.
   - Links camera-local tracks by temporal proximity, plausible store path, zone handoff, bbox scale, and optional color histogram.
   - Gives `CAM_3` entry observations priority for starting new sessions.
   - Allows unmatched non-entry observations to create low-confidence sessions rather than dropping them.
   - Records resolver evidence in `metadata.session_match_reason` and `metadata.camera_track_id`.

For the MVP, keep this heuristic and explainable. Production-grade cross-camera Re-ID can be documented as a future improvement, but the submitted funnel must not assume one independent visitor namespace per camera.

#### Event Emission

Implement `pipeline/emit.py` with a single event builder that guarantees:

- UUID v4 `event_id`.
- Required fields are always present.
- Valid `event_type`.
- Valid ISO timestamp.
- `zone_id` is null for `ENTRY`, `EXIT`, and `REENTRY` unless there is a clear zone.
- `dwell_ms` is zero for instantaneous events.
- `confidence` stays between `0.0` and `1.0`.
- `metadata.session_seq` increments per visitor session.
- `metadata.camera_track_id` is present when the event came from a camera-local track.
- `metadata.timestamp_source` records whether event time came from observed clip metadata or a documented demo assumption.

#### Entry And Exit

Use `CAM_3` as the entry/exit camera.

Approximate rule:

- Define an entry threshold polygon or line in `data/store_layout.json`.
- If a track crosses from the outer side to inner side, emit `ENTRY`.
- If a track crosses from inner side to outer side, emit `EXIT`.
- If the same approximate visitor reappears shortly after exit, emit `REENTRY` instead of a fresh unique visitor where feasible.

For the MVP, re-entry can be handled by a time-window heuristic:

- Keep recently exited tracks for 2 to 5 minutes.
- Match reappearing tracks by entry camera position, direction, approximate bounding box size, and color histogram if implemented.
- If matched, reuse the prior `visitor_id`, emit `REENTRY`, and continue the same session sequence instead of creating a second unique visitor.

#### Zone Events

For all cameras:

- Map person centroid or bottom-center point into the relevant `camera_polygons` from `data/store_layout.json`.
- If a camera has no polygon for a zone, that zone should not be inferred from that camera.
- Emit `ZONE_ENTER` when a visitor first appears in a zone.
- Emit `ZONE_EXIT` when they leave that zone.
- Emit `ZONE_DWELL` every 30 seconds of continuous dwell.

Because these clips are short, also support a lower configurable dwell interval for demo mode, such as 5 seconds. The default event schema should still document the challenge expectation of 30 seconds.

#### Billing Queue

Use `CAM_5` and `BILLING_COUNTER`.

Rules:

- Queue depth is the number of non-staff active visitors in the billing polygon.
- Emit `BILLING_QUEUE_JOIN` when a visitor enters billing and queue depth is greater than zero.
- Set `metadata.queue_depth`.
- Do not require the raw detector to know future POS state.
- Prefer deriving abandonment in the API from billing-zone exits plus POS correlation.
- If emitting `BILLING_QUEUE_ABANDON` as an event, do it in a POS-aware post-processing step over the completed event file, not during frame-by-frame detection.

#### Staff Heuristic

Staff detection is hard from the provided data, so use an explainable heuristic:

- Mark a track as likely staff if it remains in employee-side areas for a long duration.
- Increase staff score for repeated presence near billing/employee zones.
- Optionally add simple clothing color consistency if practical.
- Always include `is_staff` in events.
- Document limitations clearly in `CHOICES.md`.

### Phase 5: Event Replay

Implement `pipeline/replay.py`.

Inputs:

- `data/generated_events.jsonl`
- API URL, default `http://localhost:8000`
- batch size, default 25
- replay mode:
  - `fast`: send as quickly as possible
  - `realtime`: sleep based on event timestamp offsets
  - `demo`: sleep 0.5 to 2 seconds between batches

Behavior:

- POST batches to `/events/ingest`.
- Print accepted/rejected counts.
- Keep going on partial validation failures.
- This is what powers the live dashboard demo.

### Phase 6: API And Persistence

Implement `app/main.py` with FastAPI.

Recommended persistence:

- SQLite database file at `/data/store_intelligence.db` inside Docker.
- Tables:
  - `events`
  - `visitor_sessions` optional but recommended
  - `transactions`
  - `ingest_batches` optional

The `events` table should include:

- `event_id` primary key
- `store_id`
- `camera_id`
- `visitor_id`
- `event_type`
- `timestamp`
- `zone_id`
- `dwell_ms`
- `is_staff`
- `confidence`
- `metadata_json`
- `created_at`

If a separate `visitor_sessions` table is used, include:

- `visitor_id` primary key
- `store_id`
- `first_seen_at`
- `last_seen_at`
- `entry_at`
- `exit_at`
- `is_staff`
- `source`: `entry_camera`, `resolver_match`, or `unmatched_observation`
- `metadata_json`

The `transactions` table should include normalized POS orders:

- `transaction_id`
- `store_id`
- `timestamp`
- `basket_value_inr`
- `item_count`
- `metadata_json`

Load transactions at startup from the CSV if the table is empty.

#### POST `/events/ingest`

Requirements:

- Accept JSON body with either a raw list of events or `{ "events": [...] }`.
- Maximum batch size: 500.
- Validate each event independently.
- Deduplicate by `event_id`.
- Return partial success:

```json
{
  "accepted": 10,
  "duplicates": 2,
  "rejected": 1,
  "errors": [
    {
      "index": 3,
      "event_id": null,
      "message": "timestamp must be ISO-8601"
    }
  ]
}
```

Never return 5xx for ordinary validation failures.

#### GET `/stores/{id}/metrics`

Support optional query params:

- `start`: ISO-8601 timestamp.
- `end`: ISO-8601 timestamp.
- `window`: optional shorthand such as `latest_day`, `today`, or `last_60m`.

Return:

- `store_id`
- `window_start`
- `window_end`
- `unique_visitors`
- `conversion_rate`
- `avg_dwell_ms_by_zone`
- `current_queue_depth`
- `abandonment_rate`
- `last_event_timestamp`

Rules:

- Exclude `is_staff=true`.
- Use session-level visitor count, not raw event count.
- `unique_visitors` is the count of distinct non-staff `visitor_id` values with activity in the selected window.
- `conversion_rate` is `converted_sessions / unique_visitors`.
- A converted session is a non-staff visitor that was in `BILLING_COUNTER` within 5 minutes before a POS transaction for the same store.
- If multiple sessions are eligible for one transaction, assign the transaction to the closest eligible billing presence and count only one converted session.
- Zero purchases should return `conversion_rate: 0.0`, not null.
- Empty stores should return zeros and empty objects where appropriate.
- Default the window to the latest local business date present in events, not the machine's current calendar date. If no events exist, fall back to the current local date for the store.

#### GET `/stores/{id}/funnel`

Stages:

1. Entry
2. Zone visit
3. Billing queue
4. Purchase

Rules:

- Session is the unit.
- Re-entry should not double-count the same visitor.
- Purchase is assigned when visitor was in billing within 5 minutes before POS transaction.
- A visitor with `ENTRY` plus later `REENTRY` still contributes one count to the Entry stage.
- Zone visit means at least one `ZONE_ENTER` or `ZONE_DWELL` in a product or service zone.
- Billing queue means at least one billing-zone presence event, even if `BILLING_QUEUE_JOIN` was not emitted.
- Return counts and drop-off percentages.

#### GET `/stores/{id}/heatmap`

Return per zone:

- `zone_id`
- `visit_count`
- `avg_dwell_ms`
- `score`, normalized 0 to 100
- `data_confidence`: `LOW` if fewer than 20 sessions in the selected window, else `NORMAL`

Use a simple score:

```text
score = normalized weighted combination of visit_count and avg_dwell_ms
```

Keep it deterministic and documented.

#### GET `/stores/{id}/anomalies`

Return active anomalies:

- Queue spike.
- Conversion drop versus baseline.
- Dead zone with no visits in 30 minutes.

Each anomaly should include:

- `type`
- `severity`: `INFO`, `WARN`, or `CRITICAL`
- `message`
- `suggested_action`
- `detected_at`
- `metadata`

For the MVP:

- Queue spike if current queue depth is greater than or equal to 4, or greater than 2x recent median.
- Conversion drop if current conversion is more than 30 percent below baseline.
- Dead zone if an active product zone has no non-staff visits for 30 minutes while the store has traffic.

If no 7-day baseline exists, use same-day POS/event baseline and return a lower-confidence anomaly.

#### GET `/health`

Return:

- service status
- database status
- event count
- last event timestamp per store
- last ingest `created_at` timestamp per store
- stale feed warnings if a store has no newly ingested event in more than 10 minutes

Expose both event time and ingest time. Historical replay may contain April 2026 event timestamps, so operational feed staleness should be based on `created_at` while analytics windows should use event `timestamp`.

If the database is unavailable:

- Return HTTP 503.
- Return structured JSON.
- Do not expose raw stack traces.

### Phase 7: Structured Logging

Every request should log:

- `trace_id`
- `store_id` if present
- `endpoint`
- `latency_ms`
- `event_count` for ingest
- `status_code`

Use middleware to generate or propagate `X-Trace-Id`.

### Phase 8: Dashboard

Serve a visually polished live dashboard from FastAPI. The challenge explicitly states "Web UI scores higher" for Part E (bonus points). The dashboard must look premium and operational — not a marketing page, but not a bare HTML table either.

Target URL:

```text
http://localhost:8000/dashboard
```

Dashboard contents:

- Current unique visitors with a large hero number.
- Conversion rate gauge or percentage display.
- Current queue depth with color-coded severity.
- Last event timestamp with live countdown.
- Funnel stage counts as a visual stepped funnel.
- Heatmap as a colored zone grid or card layout.
- Active anomalies panel with severity badges.
- Health/stale feed status indicator.

Visual design:

- Dark mode with HSL-based color palette.
- CSS glassmorphism cards for each metric section.
- Smooth CSS transitions on data updates (numbers fading/counting up).
- Use a system font stack by default. If a custom font is used, vendor it locally rather than depending on Google Fonts.
- Responsive layout using CSS Grid.
- Subtle pulse animation on the "Live" indicator.

Implementation:

- Static HTML, CSS, and JavaScript — no build step.
- Avoid runtime internet dependencies. Implement simple gauges/funnel/heatmap with CSS and inline JavaScript, or vendor a small chart library locally.
- Poll API endpoints every 2 to 3 seconds using `fetch()`.
- Animate metric value transitions on each poll.
- Show connection status (green dot = connected, red = API unreachable).

The first screen must be the actual operational dashboard with real data.

### Phase 9: Tests

Use pytest and FastAPI test client.

Required behavior coverage:

- Event validation.
- Batch ingest partial success.
- Idempotency by `event_id`.
- Staff exclusion.
- Zero visitors.
- Zero purchases.
- Re-entry deduplication in funnel.
- Cross-camera session deduplication where one visitor appears in entry, browsing, and billing cameras.
- Metric window defaults to latest event business date for historical replay.
- Billing-to-POS purchase correlation.
- POS multi-line order aggregation counts one invoice as one transaction.
- Heatmap normalization.
- Low data confidence under 20 sessions.
- Queue spike anomaly.
- Dead zone anomaly.
- Health stale-feed warning.
- Health feed staleness uses ingest `created_at`, while analytics use event `timestamp`.
- Database unavailable returns 503.
- Pipeline emitter creates valid event schema.

Keep model inference out of unit tests. Use synthetic detections for tracker and emitter tests.

### Phase 10: Documentation

Create:

- `README.md`
- `docs/DESIGN.md`
- `docs/CHOICES.md`

`README.md` must include:

- Setup in 5 commands.
- `docker compose up`.
- How to run the detection pipeline.
- How to replay events.
- API examples.
- Dashboard URL.
- Test command.
- Known limitations.

`docs/DESIGN.md` must include:

- Architecture overview.
- Data flow from video to dashboard.
- Event schema.
- Storage model.
- Metric calculation rules.
- Failure handling.
- Section titled `AI-Assisted Decisions`.

`docs/CHOICES.md` must include exactly these three decisions:

1. Detection model and tracking choice.
2. Event schema design rationale.
3. API/storage architecture choice.

For each decision:

- Options considered.
- What AI suggested.
- What was chosen.
- Why.
- Known limitations.

## 5. Prompt Map

This section lists the exact AI prompts to use at each important juncture or file. Copy the relevant prompt into the AI tool, then record the accepted and modified parts in docs or test headers.

### 5.1 Prompt For Store Layout Encoding

Use when creating `data/store_layout.json`.

```text
You are helping define zones for a retail store intelligence system.

Input context:
- The store layout image shows the Brigade Bangalore Purplle store.
- CCTV cameras cover entry, main floor shelves, side/PMU area, and billing counter.
- The system needs named zones for entry/exit counting, dwell time, billing queue, and heatmap analytics.

Task:
Propose a practical JSON structure for store_layout.json with:
- store metadata
- camera IDs
- per-camera clip metadata, including clip_start_at_local and clip_start_at_utc
- zone IDs
- human-readable zone names
- floorplan_polygon_norm for dashboard display
- camera_polygons keyed by camera ID for frame-space detection
- which cameras cover each zone
- open hours

Prioritize a simple, explainable layout that supports metrics and is easy to adjust after visual inspection.
```

### 5.2 Prompt For Detection Model Decision

Use before implementing `pipeline/detect.py` and while drafting `docs/CHOICES.md`.

```text
We are building a hackathon-grade retail CCTV analytics pipeline on CPU-only Docker.

Dataset:
- Five short 1080p CCTV clips from one Purplle store.
- Need person detection, camera-local tracking, store-level visitor sessions, entry/exit counts, zone dwell, queue presence, and confidence values.
- Must be explainable in follow-up questions.

Compare these options:
1. YOLOv8n plus centroid/IoU tracking plus a lightweight global session resolver
2. OpenCV HOG/background subtraction
3. Heavier detector plus DeepSORT/Re-ID
4. Manual/synthetic event generation only

Recommend one approach for a score-oriented MVP. Include trade-offs around accuracy, runtime, implementation time, explainability, and reviewer trust.
```

Expected decision:

- Choose YOLOv8n plus centroid/IoU tracking plus a lightweight global session resolver.
- Explain that it is real CV, CPU-feasible, and easy to defend.
- Document that DeepSORT/Re-ID would be better in production but riskier in the hackathon window.

### 5.3 Prompt For Event Schema Review

Use before finalizing `app/models.py` and `pipeline/emit.py`.

```text
Review this event schema for a retail store intelligence API.

Required fields:
event_id, store_id, camera_id, visitor_id, event_type, timestamp, zone_id, dwell_ms, is_staff, confidence, metadata.

Event types:
ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY.

Task:
Suggest Pydantic validation rules and edge cases for ingestion:
- idempotency
- malformed batches
- null zone_id for entry/exit
- confidence bounds
- dwell_ms rules
- unknown event types
- batch size up to 500

Return concise recommendations that are easy to test.
```

Expected implementation:

- `confidence` must be between `0.0` and `1.0`.
- `dwell_ms` must be non-negative.
- `event_type` must be an enum.
- `zone_id` may be null only for event types that do not require a zone.
- `timestamp` must parse as timezone-aware or be normalized.
- Batch validation must support partial success.

### 5.4 Prompt For API Storage Choice

Use before implementing `app/database.py` and while drafting `docs/CHOICES.md`.

```text
We need a production-aware but hackathon-sized Store Intelligence API.

Requirements:
- docker compose up starts everything
- FastAPI endpoints for ingest, metrics, funnel, heatmap, anomalies, health
- idempotent event ingestion
- structured logs
- graceful 503 on database failure
- tests over 70 percent coverage

Compare SQLite, PostgreSQL, and in-memory storage for this challenge.
Recommend one storage choice and explain trade-offs for reliability, simplicity, scoring, and future scaling to 40 stores.
```

Expected decision:

- Choose SQLite for the MVP.
- Mention PostgreSQL as the production upgrade.
- Reject pure in-memory storage because it loses data and weakens idempotency testing.

### 5.5 Prompt For Metrics Logic

Use before implementing `app/metrics.py`, `app/funnel.py`, `app/heatmap.py`, and `app/anomalies.py`.

```text
Design deterministic business metric logic for a retail store intelligence API.

Inputs:
- event stream with visitor sessions
- POS transactions normalized from line items to order-level purchases
- staff events should be excluded
- conversion happens when a visitor was in billing within 5 minutes before a POS transaction
- event timestamps are historical and analytics endpoints should support explicit windows

Endpoints:
- metrics
- funnel
- heatmap
- anomalies

Task:
Define exact calculation rules for:
- unique visitors
- conversion rate
- historical default window behavior
- order-level POS aggregation behavior
- average dwell per zone
- current queue depth
- abandonment rate
- funnel counts and drop-off percentages
- heatmap normalization 0-100
- queue spike, conversion drop, and dead-zone anomalies

Prefer rules that are explainable, deterministic, and easy to test.
```

Expected rules:

- Use `visitor_id` as session identity.
- Exclude staff before all customer metric aggregation.
- Conversion is session-level, not event-level.
- A visitor converts if they were in billing within 5 minutes before an order timestamp.
- Re-entry keeps the same visitor session where possible.
- Default windows use the latest event business date when replaying historical data.
- Multi-line POS orders count as one transaction.
- Heatmap score combines visit frequency and dwell.

### 5.6 Prompt For Tracker And Re-Entry Logic

Use while implementing `pipeline/tracker.py`.

```text
Design a simple CPU-friendly tracker for retail CCTV people detections.

Inputs per frame:
- bounding boxes
- detection confidence
- frame timestamp
- camera ID

Need:
- stable track IDs within a camera
- store-level visitor IDs for sessions
- cross-camera matching between entry, browsing, and billing views
- approximate re-entry matching
- no heavy neural Re-ID dependency

Task:
Propose centroid/IoU matching logic, track expiration rules, a global session resolver, and a short-term re-entry heuristic.
Keep the design explainable and testable with synthetic detections.
```

Expected implementation:

- Match detections to active tracks by IoU first, then centroid distance.
- Expire missing tracks after a configurable number of frames.
- Keep camera-local `camera_track_id` separate from store-level `visitor_id`.
- Link camera-local tracks into sessions by timestamp, plausible path, zone handoff, bbox scale, and optional color histogram.
- Keep recently exited visitors in a short memory buffer.
- Reuse visitor ID if a new entry resembles a recently exited visitor within the re-entry window.

### 5.7 Prompt For Structured Logging

Use while implementing `app/logging_config.py`.

```text
Design structured request logging for a FastAPI retail analytics API.

Every request should log:
- trace_id
- store_id when available
- endpoint
- latency_ms
- event_count for ingest
- status_code

Task:
Suggest middleware structure and log field names using Python standard logging.
Also include how to propagate X-Trace-Id and avoid logging raw stack traces to clients.
```

Expected implementation:

- Middleware starts a timer.
- Generate UUID trace ID when header is absent.
- Add trace ID to response headers.
- Log one JSON-like line per request.
- Exception handlers return structured JSON.

### 5.8 Prompt For Dashboard

Use while implementing `dashboard/index.html`, `dashboard/app.js`, and `dashboard/styles.css`.

```text
Design a minimal live web dashboard for a retail store intelligence API.

Audience:
- hackathon reviewers
- operations users checking store performance

Data:
- /stores/STORE_BLR_002/metrics
- /stores/STORE_BLR_002/funnel
- /stores/STORE_BLR_002/heatmap
- /health

Task:
Propose a compact first-screen dashboard with live polling every few seconds.
Show unique visitors, conversion rate, queue depth, last event timestamp, funnel stages, heatmap zones, and health status.
Avoid marketing copy. Make it look like an operational tool.
Avoid runtime CDN, Google Fonts, or other internet dependencies.
```

Expected implementation:

- Static page served by FastAPI.
- Compact metric strip.
- Funnel row or table.
- Heatmap as colored zone cards or table.
- Health status indicator.
- CSS/JS-only visuals or locally vendored assets.
- Poll every 2 to 5 seconds.

### 5.9 Prompt For README

Use after all commands are real.

```text
Create a concise README for this Store Intelligence project.

Must include:
- setup in 5 commands
- docker compose up instructions
- how to run the detection pipeline on the CCTV clips
- how to replay generated events into the API
- API endpoint examples
- dashboard URL
- how to run tests
- notes about CPU-only operation and expected detection limitations

Use only commands that exist in this repository.
```

Important: after generating README content, manually verify every command. Do not leave aspirational commands in the README.

### 5.10 Prompt For DESIGN.md

Use while writing `docs/DESIGN.md`.

```text
Help draft the AI-Assisted Decisions section for DESIGN.md.

Context:
This project uses raw CCTV clips, a manually encoded store layout, POS transactions, a lightweight CV pipeline, FastAPI, and SQLite.

Write 2-3 concrete AI-assisted decisions:
1. Detection strategy selection
2. Event schema and validation design
3. API metrics/funnel calculation rules

For each decision, include:
- what AI suggested
- what I accepted
- what I changed or rejected
- why the final decision is appropriate for this dataset and hackathon scoring
```

Expected content:

- Specific and honest.
- Mention what was changed after AI output.
- Avoid generic claims like "AI helped optimize the architecture."

### 5.11 Prompt For CHOICES.md

Use while writing `docs/CHOICES.md`.

```text
Draft CHOICES.md for a retail CCTV store intelligence hackathon submission.

Include exactly three decisions:
1. Detection model and tracking choice
2. Event schema design rationale
3. API/storage architecture choice

For each:
- options considered
- what AI suggested
- final choice
- why the choice fits a CPU-only, Docker Compose, score-oriented MVP
- known limitations and what would improve in production
```

Expected content:

- Three clear decisions only.
- Include trade-offs.
- Include limitations.
- Make it sound like the builder understands the consequences.

## 6. Test File Prompt Blocks

Each test file must start with a prompt block. These satisfy the challenge's AI engineering requirement and should also describe manual changes.

### `tests/test_ingest.py`

```python
# PROMPT:
# Generate pytest tests for a FastAPI POST /events/ingest endpoint.
# Cover valid batch ingestion, duplicate event_id idempotency, malformed event partial success,
# batch size validation, and structured error responses.
# CHANGES MADE:
# I adjusted fixtures to match the local SQLite test database and verified expected response fields.
```

### `tests/test_metrics.py`

```python
# PROMPT:
# Generate pytest tests for store metrics from retail CCTV events and POS transactions.
# Cover unique visitors, staff exclusion, zero-purchase stores, average dwell by zone,
# billing queue depth, abandonment rate, historical default windows, and POS multi-line order aggregation.
# CHANGES MADE:
# I replaced generic examples with Brigade Bangalore store IDs and deterministic timestamps.
```

### `tests/test_funnel.py`

```python
# PROMPT:
# Generate pytest tests for a session-based retail conversion funnel.
# Cover Entry -> Zone Visit -> Billing Queue -> Purchase, re-entry deduplication,
# cross-camera visitor identity, staff exclusion, and drop-off percentage calculation.
# CHANGES MADE:
# I simplified the fixture sessions so every funnel stage can be manually verified.
```

### `tests/test_heatmap.py`

```python
# PROMPT:
# Generate pytest tests for a retail zone heatmap endpoint.
# Cover zone visit frequency, average dwell, 0-100 normalization,
# empty zones, and low data_confidence when fewer than 20 sessions exist.
# CHANGES MADE:
# I aligned zone IDs with the manually encoded store_layout.json file.
```

### `tests/test_anomalies.py`

```python
# PROMPT:
# Generate pytest tests for operational anomaly detection in a retail store API.
# Cover queue spike, conversion drop versus baseline, dead zone with no visits,
# severity values, suggested_action strings, and no-anomaly response.
# CHANGES MADE:
# I made the thresholds deterministic and documented them in the test names.
```

### `tests/test_health.py`

```python
# PROMPT:
# Generate pytest tests for a /health endpoint for a store intelligence API.
# Cover healthy service, last event timestamp per store, last ingest timestamp per store,
# stale feed warning after 10 minutes based on ingest time,
# and database unavailable returning structured HTTP 503.
# CHANGES MADE:
# I replaced mocked wall-clock behavior with injectable test timestamps.
```

### `tests/test_pipeline.py`

```python
# PROMPT:
# Generate pytest tests for a CCTV-to-events detection pipeline.
# Cover emitted event schema validity, unique event IDs, timestamp generation from frame offsets,
# confidence bounds, camera-specific zone mapping, global session resolution,
# and a short synthetic track crossing an entry threshold.
# CHANGES MADE:
# I avoided requiring a full YOLO model in unit tests by testing tracker/emitter logic with synthetic detections.
```

## 7. Acceptance Checklist

### 7.1 Mandatory Acceptance Gate (from Problem Statement)

These 5 checks must ALL pass or the submission is not scored:

1. `docker compose up` starts the API with no manual steps beyond `git clone`.
2. The README explains how to run the detection pipeline against the clips and where the output goes.
3. `POST /events/ingest` accepts events without a 5xx response.
4. `GET /stores/STORE_BLR_002/metrics` returns a valid JSON response.
5. `docs/DESIGN.md` and `docs/CHOICES.md` both exist and are non-trivial (>250 words each).

### 7.2 Full Completion Checklist

The project should not be considered complete until all of these are true:

- All 5 mandatory acceptance gate checks pass.
- `GET /health` returns valid JSON with per-store last event timestamps and last ingest timestamps.
- Detection pipeline can process at least one CCTV clip and produce JSONL events.
- `data/generated_events.jsonl` is generated from a real clip and does not serve as a hand-authored primary output.
- Duplicate ingest does not double-count events (idempotency verified).
- Dashboard is available at `/dashboard` and visually polished.
- Dashboard has no runtime CDN, Google Fonts, or external network dependency.
- Replay script updates at least one dashboard metric live.
- `pytest --cov` reaches more than 70 percent statement coverage.
- Test files include `# PROMPT:` / `# CHANGES MADE:` blocks.
- `docs/DESIGN.md` includes `AI-Assisted Decisions` section with 2-3 concrete decisions.
- `docs/CHOICES.md` covers the three required decisions with trade-offs.
- `README.md` contains verified commands only — setup in 5 commands.
- Staff events are correctly flagged `is_staff=true` and excluded from customer metrics.
- Re-entry events use `REENTRY` type with the same `visitor_id`.
- Cross-camera observations can resolve to the same store-level `visitor_id`.
- Metrics and funnel support historical `start` / `end` windows and default to the latest event business date.
- POS multi-line orders aggregate to one transaction.
- Funnel does not double-count re-entered visitors.
- Zero-traffic and zero-purchase edge cases return valid responses (not crashes or nulls).

## 8. Risks And Mitigations

### Risk: YOLO Model Download Fails

Mitigation:

- Do not require runtime internet access during reviewer execution.
- Prefer vendoring or pre-populating `models/yolov8n.pt` before final submission if repository size permits.
- If weights are not checked in, download them during Docker build when network is available and cache the model file in a dedicated build layer:
  ```dockerfile
  # Pre-download YOLO weights during build
  RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
  ```
- Include `data/generated_events.jsonl` produced from a real CCTV clip so API/demo review still works if live inference cannot run.
- Clearly document that replaying generated events is a demo path, not the primary detection path.
- Avoid CDN dependencies in the dashboard for the same reason.

### Risk: CPU Inference Is Slow

Mitigation:

- Process every Nth frame.
- Resize frames before detection.
- Allow `--max-seconds` for quick demos.
- Use event replay for dashboard demo.

### Risk: Staff Classification Is Imperfect

Mitigation:

- Use explicit heuristic scoring.
- Keep confidence values.
- Document limitations in `CHOICES.md`.
- Make metrics exclude `is_staff=true` correctly when flag is present.

### Risk: Re-Identification Is Weak

Mitigation:

- Separate camera-local `camera_track_id` from store-level `visitor_id`.
- Use a global session resolver to link likely observations across cameras.
- Use a short-term re-entry heuristic.
- Explain that production would use stronger visual Re-ID.
- Ensure funnel logic deduplicates repeated `REENTRY` events for the same `visitor_id`.

### Risk: Timestamp Windows Do Not Match POS

Mitigation:

- Store `clip_start_at_local` and `clip_start_at_utc` in `data/store_layout.json`.
- Emit UTC timestamps from frame offsets.
- Default analytics windows to the latest event business date instead of wall-clock today.
- Add explicit `start` and `end` query params to metrics endpoints.
- Test POS conversion using deterministic historical timestamps from `2026-04-10`.

### Risk: Challenge Data Differs From Prompt

Mitigation:

- Document discovered local dataset facts in `DESIGN.md`.
- Create local `store_layout.json`.
- Normalize the provided POS file rather than assuming the generic schema.

## 9. Suggested Build Order

Build in this exact order to keep the project shippable at every stage:

1. Scaffold folders, requirements, Dockerfile, and `docker-compose.yml`.
2. Create `data/store_layout.json` with camera-specific polygons and clip timestamp metadata.
3. Implement event schema in `app/models.py`.
4. Implement SQLite persistence and `/health`.
5. Implement `/events/ingest` with idempotency.
6. Add POS normalization with order-level aggregation.
7. Implement metrics, funnel, heatmap, and anomalies with explicit historical window handling.
8. Add API tests.
9. Implement camera-local tracker and event emitter with synthetic tests.
10. Add global session resolver tests for cross-camera visitor identity.
11. Add YOLO detection path.
12. Run one clip through the pipeline and create `data/generated_events.jsonl`.
13. Add replay script.
14. Add dashboard with no runtime CDN dependency.
15. Write README, DESIGN.md, and CHOICES.md.
16. Run full tests and docker smoke test.
17. Replay generated events into the API and verify the dashboard updates.

This order ensures the API and scoring-critical behavior are stable before spending time tuning computer vision.
