FROM python:3.10-slim

# Install kubernetes client library
RUN pip install --no-cache-dir kubernetes

# Set working directory
WORKDIR /app

# Copy syncer script
COPY syncer.py /app/syncer.py

# Default command to run the syncer
CMD ["python", "/app/syncer.py"]
