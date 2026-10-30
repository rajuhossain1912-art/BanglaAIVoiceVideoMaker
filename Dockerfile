FROM python:3.11-slim

# Make the web-service listening port explicit to Render's Docker port scanner.
EXPOSE 10000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORK_DIR=/tmp/bangla-video-jobs

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg espeak-ng fonts-noto-core fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /service
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
WORKDIR /service/backend
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
