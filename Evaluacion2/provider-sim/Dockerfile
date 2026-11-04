FROM python:3.12-slim
WORKDIR /app
COPY provider-sim/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/signing.py ./shared/signing.py
COPY provider-sim/main.py .
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
