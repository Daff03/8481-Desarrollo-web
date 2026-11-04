"""Auth Service: usuarios, contraseñas (Argon2id), sesiones opacas guardadas como hash y bloqueo por intentos.
Privado (puerto 8100 sin publicar). Solo lo llaman el gateway y clients, con la credencial de su tramo
(referencias gw-auth y auth-clients del secrets-manager). No emite cookies: eso lo hace el gateway."""
import hashlib, json, logging, os, re, secrets, time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

from shared.service_auth import make_guard

SESSION_TTL = timedelta(hours=int(os.environ.get("SESSION_TTL_HOURS", "8")))
VERIFY_TTL = timedelta(hours=24)
MAX_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCK_TIME = timedelta(minutes=int(os.environ.get("LOCK_MINUTES", "15")))
REQUIRE_EMAIL_VERIFIED = os.environ.get("REQUIRE_EMAIL_VERIFIED", "true").lower() == "true"
ROLES = {"cliente", "cajero", "administrador"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("auth")
ph = PasswordHasher()  # Argon2id con sal aleatoria incluida en el hash
DUMMY_HASH = ph.hash("dummy-password-for-timing")

_state: dict = {}


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def mask(email: str) -> str:
    user, _, dom = email.partition("@")
    return f"{user[:1]}***@{dom}"


def audit(event, **fields):
    # Nunca contraseñas, tokens ni correos completos.
    log.info(json.dumps({"ts": int(time.time()), "service": "auth", "event": event, **fields}))


def get_db():
    if "db" not in _state:
        from shared.secret_provider import SecretProvider
        provider = SecretProvider()
        _state["provider"] = provider
        password = provider.get("db-auth")["current"]
        client = MongoClient(os.environ["MONGO_URL"], username="auth", password=password,
                             authSource="auth_db", serverSelectionTimeoutMS=3000)
        _state["db"] = client["auth_db"]
    return _state["db"]


def get_provider():
    if "provider" not in _state:
        from shared.secret_provider import SecretProvider
        _state["provider"] = SecretProvider()
    return _state["provider"]


def ensure_indexes(db):
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db.sessions.create_index([("user_id", ASCENDING)])
    db.login_attempts.create_index([("updated_at", ASCENDING)], expireAfterSeconds=int(LOCK_TIME.total_seconds() * 4))


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("MONGO_URL"):
        ensure_indexes(get_db())
        if os.environ.get("SEED_ON_START", "false").lower() == "true":
            seed_staff(get_db())
    yield


app = FastAPI(title="auth", docs_url=None, redoc_url=None, lifespan=lifespan)


guard = make_guard("auth", {"gateway": "gw-auth", "clients": "auth-clients"}, get_provider)
ONLY_ADMIN = frozenset({"administrador"})


class UserIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


def check_password_policy(pw: str):
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        raise HTTPException(status_code=400, detail="La contraseña debe tener letras y números")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/users", status_code=201)
def create_user(body: UserIn, _=Depends(guard(services=("clients",), gateway=False)), db=Depends(get_db)):
    """Lo llama clients al registrar un cliente. El rol siempre es 'cliente': administradores y cajeros
    se crean con el seed, no por HTTP."""
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Correo no válido")
    check_password_policy(body.password)
    token = secrets.token_urlsafe(32)
    doc = {"email": email, "password_hash": ph.hash(body.password), "role": "cliente",
           "email_verified": False, "verify_token_hash": sha(token), "verify_expires": now() + VERIFY_TTL,
           "created_at": now()}
    try:
        res = db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Correo ya registrado")
    audit("user_created", user=str(res.inserted_id), email=mask(email))
    # El token de verificación se entrega a clients para enviarlo por correo; en BD solo queda su hash.
    return {"id": str(res.inserted_id), "verification_token": token}


@app.post("/verify-email")
def verify_email(body: TokenIn, _=Depends(guard()), db=Depends(get_db)):
    res = db.users.update_one({"verify_token_hash": sha(body.token), "verify_expires": {"$gt": now()}},
                              {"$set": {"email_verified": True}, "$unset": {"verify_token_hash": "", "verify_expires": ""}})
    if res.modified_count != 1:
        raise HTTPException(status_code=400, detail="Enlace inválido o vencido")
    return {"verified": True}


@app.post("/login")
def login(body: LoginIn, _=Depends(guard()), db=Depends(get_db)):
    email = body.email.strip().lower()
    att = db.login_attempts.find_one({"_id": email})
    if att and att.get("locked_until") and att["locked_until"] > now():
        audit("login_locked", email=mask(email))
        raise HTTPException(status_code=429, detail="Demasiados intentos")

    user = db.users.find_one({"email": email})
    ok = False
    try:
        ph.verify(user["password_hash"] if user else DUMMY_HASH, body.password)  # mismo costo exista o no el usuario
        ok = user is not None
    except (VerifyMismatchError, InvalidHashError):
        ok = False

    if not ok:
        count = (att or {}).get("count", 0) + 1
        upd = {"count": count, "updated_at": now()}
        if count >= MAX_ATTEMPTS:
            upd.update(locked_until=now() + LOCK_TIME, count=0)
        db.login_attempts.update_one({"_id": email}, {"$set": upd}, upsert=True)
        audit("login_failed", email=mask(email))
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    db.login_attempts.delete_one({"_id": email})
    if REQUIRE_EMAIL_VERIFIED and not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="Correo sin verificar")

    token = secrets.token_urlsafe(32)
    expires = now() + SESSION_TTL
    db.sessions.insert_one({"_id": sha(token), "user_id": str(user["_id"]), "role": user["role"],
                            "created_at": now(), "expires_at": expires})
    audit("login_ok", user=str(user["_id"]))
    return {"token": token, "expires_in": int(SESSION_TTL.total_seconds()), "role": user["role"], "user_id": str(user["_id"])}


@app.post("/session/verify")
def verify_session(body: TokenIn, _=Depends(guard()), db=Depends(get_db)):
    s = db.sessions.find_one({"_id": sha(body.token)})
    if not s or s["expires_at"] <= now():
        raise HTTPException(status_code=401, detail="Sesión no válida")
    return {"user_id": s["user_id"], "role": s["role"]}


@app.post("/logout", status_code=204)
def logout(body: TokenIn, _=Depends(guard()), db=Depends(get_db)):
    db.sessions.delete_one({"_id": sha(body.token)})


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, _=Depends(guard(services=("clients",), gateway=False)), db=Depends(get_db)):
    """Lo usa clients al dar de baja a un cliente (o al deshacer un registro a medias): borra la cuenta y sus sesiones."""
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if db.users.delete_one({"_id": oid}).deleted_count != 1:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.sessions.delete_many({"user_id": user_id})
    audit("user_deleted", user=user_id)


@app.get("/users")
def list_users(page: int = Query(1, ge=1, le=1000), limit: int = Query(50, ge=1, le=100),
               _=Depends(guard(roles=ONLY_ADMIN)), db=Depends(get_db)):
    """S13 (mantenedor de usuarios, solo administrador). Nunca devuelve hashes ni tokens."""
    cur = db.users.find({}).sort("created_at", ASCENDING).skip((page - 1) * limit).limit(limit)
    return [{"id": str(u["_id"]), "email": u["email"], "role": u["role"], "email_verified": u.get("email_verified", False)} for u in cur]


def seed_staff(db):
    """Cuentas de personal para la demo. Las contraseñas vienen del entorno (las genera gen_secrets.py en secrets/seed.env);
    sin ellas no se crea nada, así no hay credenciales por defecto en el repositorio."""
    for email, role, var in (("admin@alsahara.cl", "administrador", "SEED_ADMIN_PASSWORD"),
                             ("cajero@alsahara.cl", "cajero", "SEED_CAJERO_PASSWORD")):
        pw = os.environ.get(var)
        if pw and not db.users.find_one({"email": email}):
            db.users.insert_one({"email": email, "password_hash": ph.hash(pw), "role": role, "email_verified": True, "created_at": now()})
            audit("staff_seeded", role=role)
