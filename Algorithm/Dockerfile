FROM python:3.11-slim

ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    poppler-utils \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY server1111.py /app/
COPY invoice_validator_with_rules_Version1.py /app/
COPY rule_config.json /app/
COPY metrics_data.csv /app/
COPY training_metrics.csv /app/
COPY model_6_focus/ /app/model_6_focus/

RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    fastapi uvicorn httpx python-dotenv pillow pandas \
    pdf2image pytesseract pypdfium2 \
    torch torchvision torchaudio \
    transformers

ENV TESSERACT_CMD=/usr/bin/tesseract \
    HOST=0.0.0.0 \
    DEBUG_MODE=false

EXPOSE 8001

CMD ["sh", "-c", "uvicorn server1111:app --host 0.0.0.0 --port ${PORT:-8001}"]
