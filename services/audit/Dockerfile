# audit-service: the agent loop, the second pass and the guardrails.
# Slow and CPU-bound - this is the one that needs the resources.
# Multi-stage: the wheels are built once, then copied into a slim runtime.
FROM python:3.14-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
# Line 3 of requirements.txt is `-e .`, so the install builds this project
# too. That needs the package source and the readme pyproject names, not
# just the metadata files.
COPY pyproject.toml uv.lock requirements.txt README.md ./
COPY src/ ./src/
RUN uv pip install --system --no-cache -r requirements.txt

FROM python:3.14-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# core/ is the shared library. Every Python service copies the same one rather
# than reimplementing a rule.
COPY core/ ./core/
COPY api/ ./api/
COPY services/ ./services/
COPY data/clauses.json data/non_payable.json ./data/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "services.audit.main:app", "--host", "0.0.0.0", "--port", "8000"]
