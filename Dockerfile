FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
# run as an unprivileged user; only the data folder is writable
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/data && chown appuser:appuser /srv/data
USER appuser

ENV DATABASE_URL=sqlite:///./data/app.db PORT=8000 FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/healthz', timeout=4)"
CMD ["sh", "-c", "exec uvicorn app.asgi:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS} --no-server-header"]
