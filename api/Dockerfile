# Use official Python runtime
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ /app/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose port for the application
EXPOSE 8000

# Environment variables for configuration
ENV WORKERS=4

# Run with Gunicorn for production (multiple workers)
CMD gunicorn botapi.asgi:application \
    --bind 0.0.0.0:8000 \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --max-requests-jitter 100 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    --log-level $LOG_LEVEL \
    --timeout 60 \
    --keep-alive 5
