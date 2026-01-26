# Lightweight Dockerfile for aneya backend on Google Cloud Run
# Uses ElevenLabs and Sarvam AI for transcription (no local models required)
FROM --platform=linux/amd64 python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (including ffmpeg for audio conversion and Playwright dependencies)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    ffmpeg \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional fonts for Playwright (replacements for deprecated packages)
RUN apt-get update && apt-get install -y \
    fonts-unifont \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (Chromium for PDF generation)
RUN playwright install chromium

# Set Playwright environment variable
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Copy application code
COPY api.py .
COPY pdf_generator.py .
COPY pdf_generator_headless.py .
COPY build_react_bundle.py .
COPY custom_forms_api.py .
COPY historical_forms_api.py .
COPY doctor_logo_api.py .
COPY servers/ ./servers/
COPY mcp_servers/ ./mcp_servers/
COPY tools/ ./tools/
COPY models/ ./models/
COPY migrations/ ./migrations/
COPY historical_forms/ ./historical_forms/
COPY static/ ./static/

# Create a non-root user
RUN useradd -m -u 1000 aneya && chown -R aneya:aneya /app
USER aneya

# Expose port 8080
EXPOSE 8080

# Run the application with uvicorn on port 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
