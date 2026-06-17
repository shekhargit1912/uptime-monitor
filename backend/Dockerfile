FROM python:3.12-slim

# Keep Python output unbuffered so logs show up immediately in `docker compose`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user. /data is the SQLite volume mount point; a named volume
# inherits this ownership on first creation, so appuser can write the DB file.
RUN useradd --system --uid 10001 appuser \
    && mkdir -p /data && chown appuser /data
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
