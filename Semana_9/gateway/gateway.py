import os
import secrets
from fastapi.params import Depends
import httpx

from fastapi import(
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response
    )

from fastapi.security import(
    HTTPBearer,
    HTTPAuthorizationCredentials
)

app = FastAPI(title = "Local API Gateway")


security = HTTPBearer(
    auto_error=False
)

VAULT_ADDR = os.getenv(
    "VAULT_ADDR", "http://127.0.0.1:8200"
)

VAULT_TOKEN = os.getenv(
    "VAULT_TOKEN"
)

BACKEND_URL = "http://localhost:9000"  # fastapi

if not VAULT_TOKEN:
    raise RuntimeError("" \
    "VAULT_TOKEN no esta configurado"
    )

#Obtener secreto de Vault
async def get_gataway_secret():
    url = (
        f"{VAULT_ADDR}" 
        "/v1/secret/data/gateway"
    )
    headers = {
        "X-Vault-Token": VAULT_TOKEN
    }

    async with httpx.AsyncClient(
        timeout=5.0
        ) as client:
        response = await client.get(
            url, 
            headers=headers
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="No fue posible acceder a Vault"
        )
    vault_response = response.json()
    return vault_response[
        "data"
    ][
        "data"
    ]

async def authenticate_client(
        credentials: 
            HTTPAuthorizationCredentials 
            = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token requerido"
        )
    vault_secret = (
        await get_gataway_secret()
    )
    expected_token = vault_secret[
        "client_token"
    ]
    recieved_token = (
        credentials.credentials
    )

    valid = secrets.compare_digest(
        recieved_token,
        expected_token
    )

    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Token invalido"
        )
    return {
        "client_id": "student_client",
        "backend_secret": vault_secret[
            "backend_shared_secret"
        ]
    }

#https://localhost:8000/api/products
#@app.get("/api/products")
#async def get_products():
#    async with httpx.AsyncClient() as client:
#       response = await client.get(f"{BACKEND_URL}/products")
#        return response.json()

#@app.get("/api/orders")
#async def get_orders():
#   async with httpx.AsyncClient() as client:
#        response = await client.get(f"{BACKEND_URL}/orders")
#        return response.json()

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])

async def proxy(
    path: str, 
    request: Request, 
    auth = Depends(authenticate_client)
):
    target_url = (
        f"{BACKEND_URL}/{path}"
    )
    body = await request.body()

    gataway_headers = {
        "X-Backend-Secret": 
            auth["backend_secret"],
        "X-Authenticated-Client": 
            auth["client_id"]
    } 

    content_type = request.headers.get(
        "content-type"
    )
    if content_type:
        gataway_headers[
            "content-type"
        ] = content_type
    try:
        async with httpx.AsyncClient(
            timeout=10.0
        ) as client:
            upstream = await client.request(
                method = request.method,
                url = target_url,
                params = request.query_params,
                content = body,
                headers = gataway_headers
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Backend no disponible"
        )

    response_headers = {}
    if "content-type" in upstream.headers:
        response_headers[
            "content-type"
        ] = upstream.headers["content-type"]

    return Response(
        content = upstream.content,
        status_code = upstream.status_code,
        headers = response_headers
    )