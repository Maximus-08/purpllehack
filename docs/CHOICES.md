# Engineering Choices

## 1. Detection Model & Tracker
* yolov8n + centroid/IoU matching
* yolov8n is fast on CPU inside Docker. custom tracker is easy to explain. gives direct track lifecycle control.
* limitations: no visual re-identification. struggles with occlusion.
* alternatives: opencv HOG (poor accuracy), yolov8m + DeepSORT (too slow on CPU).

## 2. Event Schema
* flat event schema matching challenge spec
* simple stream ingestion. easy to validate. session grouping happens on the database layer.
* limitations: separate camera tracks are resolved by heuristics instead of visual features.

## 3. Storage
* sqlite with WAL
* single file database. zero container setup overhead. WAL allows concurrent reads during replay writes.
* limitations: single writer lock. production requires PostgreSQL.
