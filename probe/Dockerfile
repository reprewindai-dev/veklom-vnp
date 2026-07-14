FROM python:3.11-slim

WORKDIR /probe
COPY probe/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY probe /probe

ENV NODE_KEY_DIR=/var/lib/vnp-node
ENV TARGETS_FILE=/probe/targets.json
VOLUME ["/var/lib/vnp-node"]

ENTRYPOINT ["python", "-m", "probe.entrypoint"]
