FROM python:3.13-slim

ARG PIP_DEFAULT_TIMEOUT=100
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake embedding weights into the image so runtime never needs the network.
# Kept before COPY so everyday code changes don't invalidate this cache layer.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV FASTEMBED_CACHE_PATH=/app/.fastembed \
    EMBEDDING_MODEL=${EMBEDDING_MODEL}
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBEDDING_MODEL}')"

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]