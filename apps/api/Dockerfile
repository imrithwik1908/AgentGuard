FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY alembic ./alembic
COPY alembic.ini ./
COPY agentguard_api ./agentguard_api

CMD ["sh", "-c", "alembic upgrade head && uvicorn agentguard_api.main:app --host ${AGENTGUARD_API_HOST:-0.0.0.0} --port ${AGENTGUARD_API_PORT:-8000}"]

