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

AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL", "http://127.0.0.1:8100"
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
    gateway_secret = (
        await get_gataway_secret()
    )
    introspection_secret = (
        gateway_secret["auth_introspection_secret"]
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/introspect",
                json={"token": credentials.credentials} , 
                headers={
                    "X-Gateway_Auth_Secret" : introspection_secret
                }
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Servicio de autenticacion no disponible"
        )
    identity = response.json()
    if not identity.get("active" , False):
        raise HTTPException(
            status_code=401,
            detail="Token invalido o expirado"
        )
    return {
        "user_id": identity["user_id"],
        "username": identity["username"],
        "roles": identity["roles"],
        "backend_secret": gateway_secret["backend_secret"],
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
            auth["client_id"],
        "X-Authenticated-User": 
            auth["username"],
        "X-Authenticated-Roles":
            ",".join(auth["roles"])
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