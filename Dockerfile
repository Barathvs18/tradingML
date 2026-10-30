FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Install python dependencies
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# Copy the rest of the application
COPY . .
RUN useradd --uid 10001 --create-home appuser && mkdir -p /app/storage && chown appuser:appuser /app/storage
USER appuser

# Command is handled by docker-compose for dev, but provide a default for prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
