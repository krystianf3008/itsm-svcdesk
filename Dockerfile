FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

WORKDIR /app

# Lab 5 triage (CI-SPEC.md P-04): keep the OS packages current, so the image gate's Trivy scan starts from a base
# with as few fixable CVEs as possible.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Dependencies first, so Docker caches this layer while the code changes. Everything is installed at build time:
# the service needs no network once the image exists. pip itself is removed afterwards: svcdesk never calls pip at
# run time, and pip vendors its own old copies of a few packages (pip/_vendor) that Trivy flags as HIGH/CRITICAL
# with a fix no pip release ships yet - removing pip removes that whole class of finding.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && pip uninstall -y pip

COPY src/ /app/src/

# The SQLite file lives on the named volume mounted at /data (docker-compose.yml).
RUN mkdir -p /data

# Lab 5 triage: Semgrep's dockerfile.security.missing-user.missing-user flags a container that would otherwise
# run as root. svcdesk needs no root privilege at run time, so it drops to a dedicated user; /app and /data are
# owned by that user so it can still read the code and write the SQLite file on the named volume.
RUN useradd --system --no-create-home --uid 10001 svcdesk && chown -R svcdesk:svcdesk /app /data
USER svcdesk

ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
