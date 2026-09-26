FROM python:3.13-slim

WORKDIR /app

# Dependencies first, so Docker caches this layer while the code changes. Everything is installed at build time:
# the service needs no network once the image exists.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

# The SQLite file lives on the named volume mounted at /data (docker-compose.yml).
RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
