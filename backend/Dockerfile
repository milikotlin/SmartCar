# SRS asked for python:3.11-slim; the final ML libraries (numpy 2.5, xgboost 3.4) require Python >= 3.12, and the
# models were trained with exactly these versions, so the image uses 3.13 (change documented in docs/SRS_v2.md).
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/app"]
