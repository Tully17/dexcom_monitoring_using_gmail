FROM python:3.12-slim

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Send Python output directly to Docker logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    pydexcom \
    requests

# Copy application
COPY dexcom_monitor.py /app/dexcom_monitor.py

# Create directory for persistent logs
RUN mkdir -p /data/logs

# Run the monitor
CMD ["python", "/app/dexcom_monitor.py"]
