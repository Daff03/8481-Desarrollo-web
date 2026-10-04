import os
import secrets  

from fastapi import ( 
    FastAPI,
    Header,
    HTTPException,
    Depends
    )

app = FastAPI(
    title ="Protected Backend API",
    description = "API ubicada en el localhost enrutada por API gateway /api/products y /api/orders"
)

INTERNAL_GATEWAY_SECRET= os.getenv(
    "INTERNAL_GATEWAY_SECRET"
)

if not INTERNAL_GATEWAY_SECRET:
    raise RuntimeError(
        "INTERNAL_GATEWAY_SECRET no esa configurado"
    )

def verify_gateway(x_gateway_secret: str = Header(default="")):
    valid = secrets.compare_digest(x_gateway_secret, INTERNAL_GATEWAY_SECRET)
    if not valid:
        raise HTTPException(
            status_code=403,
            detail="Solicitud no autorizada desde gateway"
        )


@app.get(
    "/health",
    dependencies=[Depends(verify_gateway)]
    )
def health(x_authenticated_client: str | None = Header(default=None)):
    return{
        "authenticated_client": x_authenticated_client,
        "status": "OK",
        "service": "backend API"
    }

@app.get(
    "/products",
    dependencies=[Depends(verify_gateway)]
    )
def products(x_authenticated_client: str | None = Header(default=None)):
    return{
        "authenticated_client": x_authenticated_client,
        "products": [
            {"id": 1, "name": "Hummus Tradicional", "price": 6990},
            {"id": 2, "name": "Baba Ganoush", "price": 7490},
            {"id": 3, "name": "Fatayer de Espinaca", "price": 5990}
        ]
    }    

@app.get(
    "/orders",
    dependencies=[Depends(verify_gateway)]
    )
def orders(x_authenticated_client: str | None = Header(default=None)):
    return{
        "authenticated_client": x_authenticated_client,
        "orders": [
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"}
        ]
    }