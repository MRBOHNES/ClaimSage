FROM python:3.12-slim

# System deps: build tools occasionally needed by wheels; curl for healthcheck;
# tesseract-ocr for OCR of scanned PDFs and image uploads (PyMuPDF rasterizes,
# so no ImageMagick/poppler are required).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
