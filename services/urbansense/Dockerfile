# Build from the REPO ROOT context so runtime data (data/ontology, data/processed)
# can be copied alongside the service. render.yaml sets dockerContext: .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/urbansense/pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -e .

COPY services/urbansense/app ./app
COPY services/urbansense/scripts ./scripts

RUN mkdir -p artifacts

# Baked runtime data (ontology TTL/JSON-LD + processed inputs)
COPY data/ontology ./data/ontology
COPY data/processed ./data/processed

ENV URBANSENSE_DATA_DIR=/app/data
ENV URBANSENSE_ARTIFACTS_DIR=/app/artifacts
ENV URBANSENSE_ONTOLOGY_DIR=/app/data/ontology
ENV URBANSENSE_CITYFORESIGHT_URL=http://api:8000

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
