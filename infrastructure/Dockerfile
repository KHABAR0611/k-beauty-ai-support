FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN useradd --create-home --uid 10001 app
USER app
COPY --chown=app:app data ./data
ENTRYPOINT ["python", "-m", "kbeauty_support.ingestion.audit"]
