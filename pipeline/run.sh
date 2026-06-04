#!/bin/bash
echo "Starting Purplle Store Intelligence pipeline..."
if [ -f ".venv/bin/python3" ]; then
    .venv/bin/python3 -c "from pipeline.detect import run_detection; run_detection()"
elif [ -f "venv/bin/python3" ]; then
    venv/bin/python3 -c "from pipeline.detect import run_detection; run_detection()"
else
    python3 -c "from pipeline.detect import run_detection; run_detection()"
fi

