FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG ENABLE_SEMANTIC=0
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir '.[pdf]' \
    && if [ "$ENABLE_SEMANTIC" = "1" ]; then \
         pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
         && pip install --no-cache-dir '.[semantic]'; fi \
    && useradd --create-home appuser && mkdir -p /data /home/appuser/.cache \
    && chown -R appuser:appuser /app /data /home/appuser/.cache
USER appuser
RUN python -m atlas --db /data/index.sqlite3 ingest examples/documents
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=2)"
ENTRYPOINT ["python", "-m", "atlas", "--db", "/data/index.sqlite3"]
CMD ["serve", "--bind", "0.0.0.0"]
