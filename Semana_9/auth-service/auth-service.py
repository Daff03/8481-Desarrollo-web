from datetime import datetime, timedelta, timezone
import os
import secrets

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(
    title="Authentication Service",
    description="Servicion simple de autenticacion"
)

USERS = {
    "ana": {
        "nombre": "Ana Torres",
        "gmail": "ana.torres@gmail.com",
        "password": "clave123",
        "user_id": "USR-001",
        "roles": ["user"]
    },
    "carlos": {
        "nombre": "Carlos Muñoz",
        "gmail": "carlos.munoz@gmail.com",
        "password": "clave123",
        "user_id": "USR-002",
        "roles": ["user"]
    },
    "beatriz": {
        "nombre": "Beatriz Rojas",
        "gmail": "beatriz.rojas@gmail.com",
        "password": "clave123",
        "user_id": "USR-003",
        "roles": ["user"]
    },
    "diego": {
        "nombre": "Diego Fernández",
        "gmail": "diego.fernandez@gmail.com",
        "password": "clave123",
        "user_id": "USR-004",
        "roles": ["user"]
    },
    "elena": {
        "nombre": "Elena Castro",
        "gmail": "elena.castro@gmail.com",
        "password": "clave123",
        "user_id": "USR-005",
        "roles": ["user"]
    },
    "felipe": {
        "nombre": "Felipe Soto",
        "gmail": "felipe.soto@gmail.com",
        "password": "clave123",
        "user_id": "USR-006",
        "roles": ["user"]
    },
    "gabriela": {
        "nombre": "Gabriela Reyes",
        "gmail": "gabriela.reyes@gmail.com",
        "password": "clave123",
        "user_id": "USR-007",
        "roles": ["user"]
    },
    "hector": {
        "nombre": "Héctor Vargas",
        "gmail": "hector.vargas@gmail.com",
        "password": "clave123",
        "user_id": "USR-008",
        "roles": ["user"]
    },
    "isidora": {
        "nombre": "Isidora Morales",
        "gmail": "isidora.morales@gmail.com",
        "password": "clave123",
        "user_id": "USR-009",
        "roles": ["user"]
    },
    "joaquin": {
        "nombre": "Joaquín Espinoza",
        "gmail": "joaquin.espinoza@gmail.com",
        "password": "clave123",
        "user_id": "USR-010",
        "roles": ["user"]
    },
    "karina": {
        "nombre": "Karina Fuentes",
        "gmail": "karina.fuentes@gmail.com",
        "password": "clave123",
        "user_id": "USR-011",
        "roles": ["user"]
    },
    "luis": {
        "nombre": "Luis Herrera",
        "gmail": "luis.herrera@gmail.com",
        "password": "clave123",
        "user_id": "USR-012",
        "roles": ["user"]
    },
    "marcela": {
        "nombre": "Marcela Silva",
        "gmail": "marcela.silva@gmail.com",
        "password": "clave123",
        "user_id": "USR-013",
        "roles": ["user"]
    },
    "nicolas": {
        "nombre": "Nicolás Pizarro",
        "gmail": "nicolas.pizarro@gmail.com",
        "password": "clave123",
        "user_id": "USR-014",
        "roles": ["user"]
    },
    "olivia": {
        "nombre": "Olivia Contreras",
        "gmail": "olivia.contreras@gmail.com",
        "password": "clave123",
        "user_id": "USR-015",
        "roles": ["user"]
    },
    "pablo": {
        "nombre": "Pablo Araya",
        "gmail": "pablo.araya@gmail.com",
        "password": "clave123",
        "user_id": "USR-016",
        "roles": ["user"]
    },
    "renata": {
        "nombre": "Renata Guzmán",
        "gmail": "renata.guzman@gmail.com",
        "password": "clave123",
        "user_id": "USR-017",
        "roles": ["user"]
    },
    "sebastian": {
        "nombre": "Sebastián Núñez",
        "gmail": "sebastian.nunez@gmail.com",
        "password": "clave123",
        "user_id": "USR-018",
        "roles": ["user"]
    },
    "tamara": {
        "nombre": "Tamara Ibáñez",
        "gmail": "tamara.ibanez@gmail.com",
        "password": "clave123",
        "user_id": "USR-019",
        "roles": ["user"]
    },
    "vicente": {
        "nombre": "Vicente Bravo",
        "gmail": "vicente.bravo@gmail.com",
        "password": "clave123",
        "user_id": "USR-020",
        "roles": ["user","admin"]
    },
}

SESSIONS = {}

TOKEN_LIFETIME_MINUTES = 15

AUTH_INTROSPECTION_SECRET = os.getenv(
    'AUTH_INTROSPECTION_SECRET',"gateway-auth-secret-789"
)

class LoginRequest(BaseModel):
    username: str
    password: str

class instrospectionRequest(BaseModel):
    token: str

@app.post("/login")
def login(
    request: LoginRequest,x_gateway_auth_secret: str = Header(default="")
):
    if not secrets.compare_digest(
        x_gateway_auth_secret,
        AUTH_INTROSPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Gateway no autorizado"
        )
    user = USERS.get(request.username)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario incorrecto"
        )
    if user["password"] != request.password:
        raise HTTPException(
            status_code=401,
            detail="credenciales incorrectas"
        )
    acces_token = secrets.token_urlsafe(32)
    expiration = (datetime.now(timezone.utc)) + timedelta(minutes=TOKEN_LIFETIME_MINUTES)
    SESSIONS[acces_token] = {
        "user_id" :user["user_id"],
        "username": request.username,
        "roles" : user["roles"],
        "expires_at": expiration
    }
    return{
        "access_token": acces_token,
        "token_type" : "bearer",
        "expires_in": TOKEN_LIFETIME_MINUTES*60
    }

@app.post("/introspect")
def introspect(
    request: instrospectionRequest,
    x_gateway_auth_secret: str = Header(default="")
):
    if not secrets.compare_digest(
        x_gateway_auth_secret,
        AUTH_INTROSPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Gateway no autorizado"
        )
    session = SESSIONS.get(request.token)
    if session is None:
        return{
            "active": False
        }
    if (datetime.now(timezone.utc) > session["expires_at"]):
        SESSIONS.pop(request.token, None)
        return {
            "active": False
        }
    return {
        "active" : True,
        "user_id" :session["user_id"],
        "username": session["username"],
        "roles" : session["roles"],
        "expires_at": session["expires_at"].isoformat()
    }

@app.post("/logout")
def logout(
    request: instrospectionRequest,
    x_gateway_auth_secret: str = Header(default="")
):
    if not secrets.compare_digest(
        x_gateway_auth_secret,
        AUTH_INTROSPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Gateway no autorizado"
        )
    SESSIONS.pop(request.token, None)
    return {
        "message": "sesion finalizada"
    }

@app.get("/health")
def health(x_gateway_auth_secret: str = Header(default="")):
    if not secrets.compare_digest(
        x_gateway_auth_secret,
        AUTH_INTROSPECTION_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Gateway no autorizado"
        )
    return{
        "status": "OK",
        "service": "Authenticacion service"
    }