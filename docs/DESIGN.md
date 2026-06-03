# Store Intelligence Architecture Design

System architecture for the offline retail store intelligence pipeline.

## System Architecture

The pipeline processes raw camera data and aggregates retail business metrics.

### 1. Ingestion Layer
FastAPI receives event batches via POST requests. Validates payloads using Pydantic schemas. Returns structured validation errors. Enforces idempotency via unique event IDs.

### 2. Database Persistence
SQLite stores events and transactions. Write-ahead logging is enabled. Prevents query blocking during write operations. Connection pool timeout is set to ten seconds.

### 3. Business Analytics Engine
Computes real-time conversion and queue performance. Normalizes POS records. Excludes staff activity from customer metrics. Computes historical window queries.

---

## Component Specifications

### 1. Event Stream Schema
Flat JSON structures represent customer actions. Required parameters include event_id, store_id, camera_id, visitor_id, event_type, timestamp, zone_id, dwell_ms, is_staff, confidence, and metadata.

### 2. Database Storage Structure
SQLite schema contains two primary tables:
- `events`: Stores visitor detections. Indexed by event_id. Columns map to Pydantic attributes.
- `transactions`: Stores POS purchases. Indexed by transaction_id. Seeds from CSV on startup.

### 3. Metric Calculations
- `unique_visitors`: Total unique customer visitor_id values. Excludes staff.
- `conversion_rate`: Ratio of converted sessions to unique visitors. A session converts when visitor billing events happen within five minutes before a transaction timestamp. Pairing assigns the transaction to the closest billing event visitor.
- `average_dwell_ms_by_zone`: Mean dwell time of customers per zone.
- `current_queue_depth`: Highest active queue depth parameter from join events.
- `abandonment_rate`: Ratio of billing visitors who exit without making a purchase.

### 4. Database Failure Handling
Unreachable database states return HTTP 503. Client receives JSON error responses. Raw Python stack traces are suppressed.

---

## AI-Assisted Decisions

### 1. Video Timeline Alignment
The AI suggested aligning clips to transaction times. We set clip start times to 16:53:30 local on 2026-04-10. This ensures Visitor 1 converts at cash counter within the video window.

### 2. Database Persistence Selection
The AI suggested PostgreSQL. We chose SQLite with WAL mode. SQLite is simpler for local execution. WAL mode handles concurrent reads and writes.

### 3. Funnel Pairing Logic
The AI suggested basic temporal matching. We implemented a greedy closest-presence matching algorithm. This prevents multiple sessions from claiming the same transaction.
