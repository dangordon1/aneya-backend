# Multi-stage build for aneya backend on Google Cloud Run
FROM --platform=linux/amd64 python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install PyTorch CPU-only FIRST to avoid pulling in CUDA dependencies (~2GB)
# This ensures nemo-toolkit uses CPU-only PyTorch instead of GPU version
# Use exact CPU wheel versions from PyTorch's CPU index
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
# nemo-toolkit will now use the CPU-only PyTorch installed above
RUN pip install --no-cache-dir -r requirements.txt

# Note: Parakeet model will be downloaded on first startup (~3-5 min)
# Cloud Run has 10-minute startup timeout, which is sufficient
# Model is cached after first download for instant subsequent startups

# Copy application code (maintain directory structure)
COPY backend/ ./backend/
COPY servers/ ./servers/

# Create a non-root user
RUN useradd -m -u 1000 aneya && chown -R aneya:aneya /app
USER aneya

# Expose port 8080
EXPOSE 8080

# Run the application with uvicorn on port 8080
# Using exec form (JSON array) to prevent shell variable expansion
# This ensures Railway cannot inject PORT variable into the command
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
