from fastapi import FastAPI
import httpx

app = FastAPI(title = "Local API Gateway")

BACKEND_URL = "http://localhost:9000"  # fastapi

#https://localhost:8000/api/products
@app.get("/api/products")
async def get_products():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/products")
        return response.json()

@app.get("/api/orders")
async def get_orders():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_URL}/orders")
        return response.json()