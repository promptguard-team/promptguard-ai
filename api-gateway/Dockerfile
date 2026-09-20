# Base
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS base

RUN pip install --no-cache-dir --upgrade pip setuptools wheel>=0.46.2 jaraco.context>=6.1.0

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel>=0.46.2 jaraco.context>=6.1.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development
FROM base AS dev

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production
FROM base AS prod

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
