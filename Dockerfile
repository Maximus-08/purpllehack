FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp

# Set work directory
WORKDIR /app

# Install system dependencies (only runtime libs for OpenCV, no compilation tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first and immediately prune unused files to save layer space
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    rm -rf /usr/local/lib/python3.12/site-packages/torch/test \
           /usr/local/lib/python3.12/site-packages/torch/include

# Install python dependencies and immediately uninstall dev libraries in the same layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pytest pytest-cov httpx && \
    find /usr/local/lib/python3.12/site-packages -name "__pycache__" -type d -exec rm -rf {} +

# Pre-download YOLOv8n weights during build to run offline
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
