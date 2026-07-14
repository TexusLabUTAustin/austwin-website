# Build from the REPO ROOT context so runtime data (data/processed) can be
# copied alongside the service. render.yaml sets dockerContext: .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/cityforesight/pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -e .

COPY services/cityforesight/app ./app
COPY services/cityforesight/training ./training
COPY services/cityforesight/scripts ./scripts

# Baked runtime model + metrics (tracked in git via .gitignore negations)
COPY services/cityforesight/artifacts ./artifacts
# Baked runtime data (tracts geojson, morphology, historical ASOS)
COPY data/processed ./data/processed

ENV CITYFORESIGHT_DATA_DIR=/app/data
ENV CITYFORESIGHT_ARTIFACTS_DIR=/app/artifacts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
