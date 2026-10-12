# Base
FROM python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2 AS base

RUN pip install --no-cache-dir --upgrade pip setuptools wheel>=0.46.2 jaraco.context>=6.1.0

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"

# Builder
FROM base AS builder

RUN python -m venv /opt/venv

RUN pip install --no-cache-dir --upgrade pip setuptools wheel>=0.46.2 jaraco.context>=6.1.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development
FROM base AS dev

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000", "--reload"]

# Production
FROM base AS prod

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser models ./models

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]
