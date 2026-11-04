FROM python:3.12.16-slim
WORKDIR /app
COPY svc-orders/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY svc-orders/main.py svc-orders/coverage.json ./
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8500
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500"]
