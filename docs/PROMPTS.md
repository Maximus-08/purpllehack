# Prompt Playbook (Draft)

*This document records the exact prompts used to guide the development of this system.*

## Phase 1: Scaffolding and Setup
### Prompt 1.1: Project Skeleton Scaffolding
```text
Scaffold the project skeleton, create requirements.txt, Dockerfile, and docker-compose.yml.

Set up the full directory structure from the implementation plan: app/, pipeline/, dashboard/, data/, tests/, and docs/. Create all __init__.py files, empty module stubs, and the dependency files. The Dockerfile should use Python 3.12 slim, pre-download YOLOv8n weights during build, and run uvicorn. docker-compose.yml should map port 8000 and volume for SQLite persistence.
```
*Response*: Created requirements, docker configs, pytest config, app directories, pipeline directories, dashboard files, data folder, and test file stubs.
