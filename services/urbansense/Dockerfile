FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system -e .

COPY app ./app
COPY scripts ./scripts

RUN mkdir -p artifacts

ENV URBANSENSE_DATA_DIR=/app/data
ENV URBANSENSE_ARTIFACTS_DIR=/app/artifacts
ENV URBANSENSE_ONTOLOGY_DIR=/app/data/ontology
ENV URBANSENSE_CITYFORESIGHT_URL=http://api:8000

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
