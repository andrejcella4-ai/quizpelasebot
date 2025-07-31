# Use official Python runtime
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ /app/

# Expose port for the application
EXPOSE 8000

# Run the ASGI server
CMD ["uvicorn", "botapi.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
