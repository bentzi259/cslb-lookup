FROM python:3.11-slim AS base

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY scripts/ scripts/
RUN chmod +x scripts/*.sh

RUN mkdir -p /data && chown appuser:appuser /data

USER appuser

EXPOSE 8000

ENV DATABASE_PATH=/data/licenses.db

ENTRYPOINT []
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
