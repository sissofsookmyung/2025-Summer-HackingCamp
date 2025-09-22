
FROM python:3.9-slim


ENV DEBIAN_FRONTEND=noninteractive
ENV FLASK_ENV=production \
    FLASK_DEBUG=0 \
    BASE_URL=http://127.0.0.1:808 \
    DB_PATH=/app/db.sqlite \
    BOT_WAIT_SEC=5.0


RUN apt-get update -y && apt-get install -y \
    chromium \
    chromium-driver \
    sqlite3 \
    build-essential \
    python3-dev \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY flag.txt /flag.txt
RUN chmod 644 /flag.txt


RUN groupadd -r appuser && useradd --no-log-init -r -g appuser -m appuser
RUN chown -R appuser:appuser /app

USER appuser


CMD ["python3", "app.py"]
