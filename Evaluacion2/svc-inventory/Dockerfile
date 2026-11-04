FROM python:3.12-slim
WORKDIR /app
COPY svc-inventory/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY svc-inventory/main.py svc-inventory/seed.py ./
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8400
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8400"]
