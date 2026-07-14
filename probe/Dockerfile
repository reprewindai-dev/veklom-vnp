FROM python:3.11-slim

WORKDIR /app
COPY probe/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY probe /app/probe

ENV NODE_KEY_DIR=/var/lib/vnp-node
ENV TARGETS_FILE=/app/probe/targets.json
VOLUME ["/var/lib/vnp-node"]

ENTRYPOINT ["python", "-m", "probe.entrypoint"]
