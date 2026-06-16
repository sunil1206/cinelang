FROM python:3.12-slim

WORKDIR /app

# System deps (httpx needs these for SSL)
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Persistent volume for SQLite
RUN mkdir -p /data
ENV DB_PATH=/data/cinelang.db

EXPOSE 8000

# Run Alembic migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
