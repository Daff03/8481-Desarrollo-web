"""clients: autoridad de los datos personales del cliente (RUN, contacto, direcciones). Privado (8300).
El registro orquesta a auth: crea la cuenta allí y guarda el perfil aquí. La verificación de correo sale por ActiveMQ
mediante un outbox, así un broker caído no pierde el aviso. Solo el propio cliente ve su perfil completo."""
import asyncio, json, logging, os, re, time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from shared.events import EventBus, EventBusUnavailable
from shared.service_auth import make_guard

CLIENTE = frozenset({"cliente"})
ADMIN, STAFF = frozenset({"administrador"}), frozenset({"cajero", "administrador"})
MAX_ADDRESSES = 5
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("clients")
_state: dict = {}


class AuthConflict(Exception): ...
class AuthRejected(Exception): ...
class AuthDown(Exception): ...


def get_provider():
    if "provider" not in _state:
        from shared.secret_provider import SecretProvider
        _state["provider"] = SecretProvider()
    return _state["provider"]


def get_db():
    if "db" not in _state:
        from shared import db
        _state["db"] = db.connect(get_provider(), "clients")
    return _state["db"]


class AuthClient:
    """Llamadas de clients a auth con la credencial del tramo (referencia auth-clients)."""
    def __init__(self, provider):
        self.provider, self.base = provider, os.environ.get("AUTH_URL", "http://auth:8100")

    def _headers(self):
        return {"X-Caller": "clients", "X-Caller-Key": self.provider.get("auth-clients")["current"]}

    def create_user(self, email, password):
        try:
            r = httpx.post(f"{self.base}/users", json={"email": email, "password": password}, headers=self._headers(), timeout=4)
        except Exception as exc:
            raise AuthDown() from exc
        if r.status_code == 201:
            return r.json()["id"], r.json()["verification_token"]
        raise {409: AuthConflict, 400: AuthRejected}.get(r.status_code, AuthDown)()

    def delete_user(self, user_id):
        try:
            httpx.delete(f"{self.base}/users/{user_id}", headers=self._headers(), timeout=4)
        except Exception as exc:
            raise AuthDown() from exc


def get_auth():
    return AuthClient(get_provider())


def get_bus():
    return EventBus(get_provider(), "clients")


guard = make_guard("clients", {"gateway": "gw-clients", "orders": "orders-clients"}, get_provider)


def audit(event, **f):
    log.info(json.dumps({"ts": int(time.time()), "service": "clients", "event": event, **f}))  # sin RUN, correo ni teléfono


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ outbox de correos
def flush_outbox(db, bus) -> int:
    """Publica los eventos pendientes; al publicarse se borra el documento (así el token de verificación no queda guardado)."""
    sent = 0
    for doc in list(db.outbox.find({}).sort("created_at", ASCENDING).limit(50)):
        try:
            bus.publish(doc["type"], doc["payload"], event_id=doc["_id"])
        except EventBusUnavailable:
            break
        db.outbox.delete_one({"_id": doc["_id"]})
        sent += 1
    return sent


async def _outbox_loop():
    while True:
        await asyncio.sleep(30)
        try:
            await asyncio.to_thread(flush_outbox, get_db(), get_bus())
        except Exception as exc:
            log.error(json.dumps({"event": "outbox_failed", "error": type(exc).__name__}))


def ensure_indexes(db):
    db.clients.create_index([("run", ASCENDING)], unique=True)
    db.clients.create_index([("user_id", ASCENDING)], unique=True, sparse=True)  # clientes de local no tienen cuenta
    db.addresses.create_index([("client_id", ASCENDING)])


@asynccontextmanager
async def lifespan(app):
    task = None
    if os.environ.get("MONGO_URL"):
        ensure_indexes(get_db())
        task = asyncio.create_task(_outbox_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="clients", docs_url=None, redoc_url=None, lifespan=lifespan)


# ------------------------------------------------------------------ validaciones
def normalize_run(run: str) -> str:
    return re.sub(r"[.\s]", "", run).upper()


def valid_run(run: str) -> bool:
    m = re.fullmatch(r"(\d{7,8})-([\dK])", run)
    if not m:
        return False
    total, mult = 0, 2
    for d in reversed(m.group(1)):
        total += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    dv = 11 - total % 11
    return {11: "0", 10: "K"}.get(dv, str(dv)) == m.group(2)


def mask_run(run: str) -> str:
    return run[:-5] + "***-" + run[-1] if len(run) > 6 and not run.startswith("baja:") else "***"


class Base(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    fechaNacimiento: date
    sexo: str
    telefono: str = Field(max_length=20)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        if len(v.split()) < 2:
            raise ValueError("Ingresa nombre y apellido")
        return " ".join(v.split())

    @field_validator("sexo")
    @classmethod
    def _sexo(cls, v):
        if v not in ("F", "M", "O"):
            raise ValueError("Sexo no válido")
        return v

    @field_validator("telefono")
    @classmethod
    def _tel(cls, v):
        v = re.sub(r"\s", "", v)
        if not re.fullmatch(r"\+?\d{9,12}", v):
            raise ValueError("Teléfono no válido")
        return v

    @field_validator("fechaNacimiento")
    @classmethod
    def _edad(cls, v):
        if v is None:
            return v
        t = date.today()
        edad = t.year - v.year - ((t.month, t.day) < (v.month, v.day))
        if not 18 <= edad < 120:
            raise ValueError("Debes ser mayor de edad")
        return v


class AddressIn(BaseModel):
    alias: str = Field(default="Casa", min_length=1, max_length=30)
    direccion: str = Field(min_length=5, max_length=120)
    comuna: str = Field(min_length=2, max_length=60)
    provincia: str = Field(min_length=2, max_length=60)
    region: str = Field(min_length=2, max_length=60)
    principal: bool = False


class RegisterIn(Base):
    run: str = Field(max_length=14)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    direccion: str = Field(min_length=5, max_length=120)
    comuna: str = Field(min_length=2, max_length=60)
    provincia: str = Field(min_length=2, max_length=60)
    region: str = Field(min_length=2, max_length=60)

    @field_validator("run")
    @classmethod
    def _run(cls, v):
        v = normalize_run(v)
        if not valid_run(v):
            raise ValueError("RUN no válido")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Correo no válido")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("La contraseña debe tener letras y números")
        return v


class ProfileIn(Base):
    """PUT /clients/me: el RUN, el correo y la fecha de nacimiento no los cambia el cliente."""
    fechaNacimiento: date | None = None


class ClientAdminIn(RegisterIn):
    """Registro en local (RF6): sin cuenta; el correo y la dirección son opcionales."""
    email: str | None = Field(default=None, max_length=254)
    password: str | None = None
    direccion: str | None = None
    comuna: str | None = None
    provincia: str | None = None
    region: str | None = None


# ------------------------------------------------------------------ DTO
def profile(c: dict) -> dict:
    return {"id": str(c["_id"]), "run": c["run"], "nombre": c["nombre"], "fechaNacimiento": c.get("fecha_nacimiento"),
            "sexo": c.get("sexo"), "telefono": c.get("telefono"), "email": c.get("email")}


def address(a: dict) -> dict:
    return {"id": str(a["_id"]), "alias": a["alias"], "direccion": a["direccion"], "comuna": a["comuna"],
            "provincia": a["provincia"], "region": a["region"], "principal": a["principal"]}


def list_item(c: dict) -> dict:
    return {"id": str(c["_id"]), "nombre": c["nombre"], "run": mask_run(c["run"]), "email": c.get("email"), "conCuenta": "user_id" in c}


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="No encontrado")


def my_client(db, principal) -> dict:
    c = db.clients.find_one({"user_id": principal.user_id, "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return c


def add_address(db, client_id: str, a: dict, principal: bool | None = None):
    n = db.addresses.count_documents({"client_id": client_id})
    if n >= MAX_ADDRESSES:
        raise HTTPException(status_code=422, detail=f"Máximo {MAX_ADDRESSES} direcciones")
    is_main = n == 0 if principal is None else (principal or n == 0)
    if is_main:
        db.addresses.update_many({"client_id": client_id}, {"$set": {"principal": False}})
    doc = {"client_id": client_id, **{k: a[k] for k in ("alias", "direccion", "comuna", "provincia", "region")},
           "principal": is_main, "created_at": now()}
    doc["_id"] = db.addresses.insert_one(doc).inserted_id
    return doc


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ registro (S03, S04)
@app.post("/clients/register", status_code=201)
def register(body: RegisterIn, _=Depends(guard()), db=Depends(get_db), auth=Depends(get_auth), bus=Depends(get_bus)):
    if db.clients.find_one({"run": body.run}):
        raise HTTPException(status_code=409, detail="Dato ya registrado")
    try:
        user_id, token = auth.create_user(body.email, body.password)
    except AuthConflict:
        raise HTTPException(status_code=409, detail="Dato ya registrado")
    except AuthRejected:
        raise HTTPException(status_code=400, detail="Datos de cuenta no válidos")
    except AuthDown:
        raise HTTPException(status_code=503, detail="Servicio no disponible")

    doc = {"user_id": user_id, "run": body.run, "nombre": body.nombre, "fecha_nacimiento": body.fechaNacimiento.isoformat(),
           "sexo": body.sexo, "telefono": body.telefono, "email": body.email, "activo": True, "created_at": now()}
    try:
        doc["_id"] = db.clients.insert_one(doc).inserted_id
        add_address(db, str(doc["_id"]), {"alias": "Principal", **body.model_dump(include={"direccion", "comuna", "provincia", "region"})})
    except Exception as exc:  # no dejar una cuenta sin perfil
        try:
            auth.delete_user(user_id)
        except AuthDown:
            audit("orphan_user", user=user_id)
        if isinstance(exc, DuplicateKeyError):
            raise HTTPException(status_code=409, detail="Dato ya registrado")
        raise
    db.outbox.insert_one({"_id": f"verif-{doc['_id']}", "type": "correo.enviar", "created_at": now(),
                          "payload": {"to": body.email, "template": "verificar_correo", "data": {"token": token}}})
    flush_outbox(db, bus)  # mejor esfuerzo; si el broker cae, el bucle de fondo reintenta
    audit("client_registered", client=str(doc["_id"]))
    return {"id": str(doc["_id"])}


# ------------------------------------------------------------------ perfil propio (S07, S08) y direcciones (S36–S39)
@app.get("/clients/me")
def get_me(p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    return profile(my_client(db, p))


@app.put("/clients/me")
def put_me(body: ProfileIn, p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    c = my_client(db, p)
    upd = {"nombre": body.nombre, "sexo": body.sexo, "telefono": body.telefono}
    db.clients.update_one({"_id": c["_id"]}, {"$set": upd})
    return profile(db.clients.find_one({"_id": c["_id"]}))


@app.get("/clients/me/addresses")
def my_addresses(p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    c = my_client(db, p)
    return [address(a) for a in db.addresses.find({"client_id": str(c["_id"])}).sort("created_at", ASCENDING)]


@app.post("/clients/me/addresses", status_code=201)
def create_address(body: AddressIn, p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    c = my_client(db, p)
    return address(add_address(db, str(c["_id"]), body.model_dump(), principal=body.principal))


def own_address(db, c, addr_id):
    a = db.addresses.find_one({"_id": oid(addr_id), "client_id": str(c["_id"])})  # la propiedad se comprueba en la consulta
    if not a:
        raise HTTPException(status_code=404, detail="Dirección no encontrada")
    return a


@app.put("/clients/me/addresses/{addr_id}")
def update_address(addr_id: str, body: AddressIn, p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    c = my_client(db, p)
    a = own_address(db, c, addr_id)
    if body.principal:
        db.addresses.update_many({"client_id": str(c["_id"])}, {"$set": {"principal": False}})
    db.addresses.update_one({"_id": a["_id"]}, {"$set": body.model_dump() | {"principal": body.principal or a["principal"]}})
    return address(db.addresses.find_one({"_id": a["_id"]}))


@app.delete("/clients/me/addresses/{addr_id}", status_code=204)
def delete_address(addr_id: str, p=Depends(guard(roles=CLIENTE)), db=Depends(get_db)):
    c = my_client(db, p)
    a = own_address(db, c, addr_id)
    db.addresses.delete_one({"_id": a["_id"]})
    if a["principal"]:  # la más antigua pasa a ser la principal
        nxt = db.addresses.find_one({"client_id": str(c["_id"])}, sort=[("created_at", ASCENDING)])
        if nxt:
            db.addresses.update_one({"_id": nxt["_id"]}, {"$set": {"principal": True}})


# ------------------------------------------------------------------ mantenedor de clientes (S09–S12)
@app.get("/clients")
def list_clients(q: str | None = Query(default=None, max_length=60), page: int = Query(1, ge=1, le=1000),
                 limit: int = Query(50, ge=1, le=100), _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    flt: dict = {"activo": True}
    if q:
        run = normalize_run(q)
        flt["$or"] = [{"run": run}, {"nombre": {"$regex": re.escape(q), "$options": "i"}}]
    cur = db.clients.find(flt).sort("nombre", ASCENDING).skip((page - 1) * limit).limit(limit)
    return [list_item(c) for c in cur]


@app.get("/clients/{client_id}")
def get_client(client_id: str, _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    c = db.clients.find_one({"_id": oid(client_id), "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return profile(c) | {"direcciones": [address(a) for a in db.addresses.find({"client_id": client_id})]}


@app.post("/clients", status_code=201)
def create_client(body: ClientAdminIn, _=Depends(guard(roles=ADMIN)), db=Depends(get_db)):
    doc = {"run": body.run, "nombre": body.nombre, "fecha_nacimiento": body.fechaNacimiento.isoformat(), "sexo": body.sexo,
           "telefono": body.telefono, "email": body.email, "activo": True, "created_at": now()}
    try:
        doc["_id"] = db.clients.insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Dato ya registrado")
    if body.direccion and body.comuna and body.provincia and body.region:
        add_address(db, str(doc["_id"]), {"alias": "Principal", "direccion": body.direccion, "comuna": body.comuna,
                                          "provincia": body.provincia, "region": body.region})
    audit("client_created_by_admin", client=str(doc["_id"]))
    return profile(doc)


@app.put("/clients/{client_id}")
def replace_client(client_id: str, body: ProfileIn, _=Depends(guard(roles=ADMIN)), db=Depends(get_db)):
    c = db.clients.find_one({"_id": oid(client_id), "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    upd = {"nombre": body.nombre, "sexo": body.sexo, "telefono": body.telefono}
    if body.fechaNacimiento:
        upd["fecha_nacimiento"] = body.fechaNacimiento.isoformat()
    db.clients.update_one({"_id": c["_id"]}, {"$set": upd})
    return profile(db.clients.find_one({"_id": c["_id"]}))


@app.delete("/clients/{client_id}", status_code=204)
def delete_client(client_id: str, _=Depends(guard(roles=ADMIN)), auth=Depends(get_auth), db=Depends(get_db)):
    """Baja con anonimización: se borran los datos personales y la cuenta. Los pedidos conservan su propia copia."""
    c = db.clients.find_one({"_id": oid(client_id), "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if c.get("user_id"):
        try:
            auth.delete_user(c["user_id"])
        except AuthDown:
            raise HTTPException(status_code=503, detail="Servicio no disponible")
    db.addresses.delete_many({"client_id": client_id})
    db.clients.update_one({"_id": c["_id"]}, {"$set": {"activo": False, "nombre": "(baja)", "run": f"baja:{client_id}",
                                                      "telefono": None, "email": None, "sexo": None, "fecha_nacimiento": None,
                                                      "deleted_at": now()}, "$unset": {"user_id": ""}})
    audit("client_deleted", client=client_id)


# ------------------------------------------------------------------ uso interno de orders
def internal_view(db, c):
    return profile(c) | {"userId": c.get("user_id"), "direcciones": [address(a) for a in db.addresses.find({"client_id": str(c["_id"])})]}


@app.get("/internal/clients/by-user/{user_id}")
def by_user(user_id: str, _=Depends(guard(services=("orders",), gateway=False)), db=Depends(get_db)):
    c = db.clients.find_one({"user_id": user_id, "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return internal_view(db, c)


@app.get("/internal/clients/{client_id}")
def by_id(client_id: str, _=Depends(guard(services=("orders",), gateway=False)), db=Depends(get_db)):
    c = db.clients.find_one({"_id": oid(client_id), "activo": True})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return internal_view(db, c)
