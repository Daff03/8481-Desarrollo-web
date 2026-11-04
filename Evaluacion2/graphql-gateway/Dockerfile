FROM python:3.12-slim
WORKDIR /app
COPY graphql-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY graphql-gateway/main.py graphql-gateway/limits.py graphql-gateway/schema.graphql ./
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8700
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8700"]
