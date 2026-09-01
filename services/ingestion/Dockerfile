# ingestion-service: PDFs to clauses to embeddings.
# Heavy but rare; it is the only image that needs the policy PDFs.
# Multi-stage: the wheels are built once, then copied into a slim runtime.
FROM python:3.14-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock requirements.txt ./
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
COPY data/policies/ ./data/policies/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "services.ingestion.main:app", "--host", "0.0.0.0", "--port", "8000"]
