FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Cloud Run injecte PORT. Timeout long : Gemini + Drive.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 120
