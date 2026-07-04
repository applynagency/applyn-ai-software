FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY artifacts/nexora-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY artifacts/nexora-api/ .

RUN node scripts/validate-frontend.js

RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data
USER appuser

ENV LOCAL_DATA_DIR=/data
ENV UVICORN_WORKERS=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
