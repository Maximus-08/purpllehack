#!/bin/bash
echo "Starting Purplle Store Intelligence pipeline..."
python3 -c "from pipeline.detect import run_detection; run_detection()"

