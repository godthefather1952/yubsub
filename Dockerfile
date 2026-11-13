FROM denoland/deno:bin-2.9.7 AS deno
FROM python:3.12-slim
COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# YouTube changes frequently. Build with the latest supported yt-dlp nightly
# (including its matching yt-dlp-ejs scripts) instead of a stale stable wheel.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade --pre "yt-dlp[default]" \
    && python -c "import yt_dlp; print('yt-dlp:', yt_dlp.version.__version__)" \
    && useradd --create-home --uid 10001 yubsub
COPY --chown=yubsub:yubsub . .
USER yubsub
ENV PORT=5000 PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:$PORT -w 1 --threads 8 --timeout 0 app:app"]