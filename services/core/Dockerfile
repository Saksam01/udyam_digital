FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    ID_VALIDATION_MODE=mock \
    AS_OF_DATE=2026-07-15 \
    DEMO_MODE=1

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
