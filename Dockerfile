FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm || true

COPY src/ ./src/
COPY dashboard.py .
COPY experiments/ ./experiments/
COPY landing.html .

RUN mkdir -p /data

ENV CACHE_DB=/data/cache.db

EXPOSE 8000

CMD ["uvicorn", "src.proxy:app", "--host", "0.0.0.0", "--port", "8000"]
