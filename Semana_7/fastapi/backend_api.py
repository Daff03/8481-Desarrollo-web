from fastapi import FastAPI

app = FastAPI(
    title ="backend API",
    description = "AP ubicada en el localhost enrutada por API gateway /api/products y /api/orders"
)

app.get("/health")
def health():
    return{
        "status": "OK",
        "service": "backend API"
    }
    
@app.get("/products")
def products():
    return {
        "products": [
            {"id": 1, "name": "Hummus Tradicional", "price": 6990},
            {"id": 2, "name": "Baba Ganoush", "price": 7490},
            {"id": 3, "name": "Fatayer de Espinaca", "price": 5990}
        ]
    }    

@app.get("/orders")
def orders():
    return  {
        "orders": {
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"}
        }
    }