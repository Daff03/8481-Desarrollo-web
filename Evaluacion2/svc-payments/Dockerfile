FROM python:3.12.16-slim
WORKDIR /app
COPY svc-payments/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY svc-payments/main.py .
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8600
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8600"]
