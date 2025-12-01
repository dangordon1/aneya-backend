FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn requests beautifulsoup4

# Copy application
COPY app.py .

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
