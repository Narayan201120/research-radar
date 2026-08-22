FROM python:3.12-slim

ARG PIP_DEFAULT_TIMEOUT=100
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]