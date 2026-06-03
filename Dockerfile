FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp

# Set work directory
WORKDIR /app

# Install system dependencies (for OpenCV and building python packages if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8n weights during build to run offline
# Ultralytics downloads them to the current directory or configuration dir, let's save it directly to /app
RUN python -c "from ultralytics import YOLO; model = YOLO('yolov8n.pt')"

# Copy application directories
COPY app/ /app/app/
COPY pipeline/ /app/pipeline/
COPY dashboard/ /app/dashboard/
COPY data/ /app/data/

# Expose API port
EXPOSE 8000

# Run FastAPI app with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
