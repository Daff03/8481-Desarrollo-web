"""payments: autoridad del estado de los pagos y única puerta de entrada del proveedor (webhook firmado). Privado (8600).
Nunca usa un monto, un estado ni un "pago exitoso" informado por el navegador: el monto sale de orders, y la aprobación llega
solo por el webhook del proveedor, verificado con HMAC, con ventana anti-repetición e idempotencia por event_id.
El pedido pasa a PAGADO únicamente cuando orders consume el evento `pago.aprobado` que este servicio publica."""
import asyncio, json, logging, os, re, secrets, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from shared import signing
from shared.events import EventBus, EventBusUnavailable
from shared.service_auth import make_guard

CLIENTE = "cliente"
ANY = frozenset({CLIENTE, "cajero", "administrador"})
STAFF = frozenset({"cajero", "administrador"})
PROVIDER_PUBLIC_URL = os.environ.get("PROVIDER_PUBLIC_URL", "http://localhost:9000").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
WEBHOOK_TOLERANCE = 300  # segundos: un aviso más viejo (o del futuro) se considera repetición
CHECKOUT_TTL = 1800

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("payments")
_state: dict = {}


class ServiceDown(Exception): ...


def get_provider():
    if "provider" not in _state:
        from shared.secret_provider import SecretProvider
        _state["provider"] = SecretProvider()
    return _state["provider"]


def get_db():
    if "db" not in _state:
        from shared import db
        _state["db"] = db.connect(get_provider(), "payments")
    return _state["db"]


class OrdersClient:
    def __init__(self, provider):
        self.provider, self.base = provider, os.environ.get("ORDERS_URL", "http://svc-orders:8500")

    def get_order(self, order_id):
        try:
            r = httpx.get(f"{self.base}/internal/orders/{order_id}", timeout=4,
                          headers={"X-Caller": "payments", "X-Caller-Key": self.provider.get("orders-payments")["current"]})
        except Exception as exc:
            raise ServiceDown() from exc
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        raise ServiceDown()


def get_orders(): return OrdersClient(get_provider())
def get_bus(): return EventBus(get_provider(), "payments")


guard = make_guard("payments", {"gateway": "gw-payments", "graphql-gateway": "gql-payments"}, get_provider)


def audit(event, **f):
    log.info(json.dumps({"ts": int(time.time()), "service": "payments", "event": event, **f}))


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def flush_outbox(db, bus) -> int:
    """Publica los `pago.aprobado` pendientes. El event_id es estable, así orders deduplica aunque se reintente."""
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
        await asyncio.sleep(15)
        try:
            await asyncio.to_thread(flush_outbox, get_db(), get_bus())
        except Exception as exc:
            log.error(json.dumps({"event": "outbox_failed", "error": type(exc).__name__}))


def ensure_indexes(db):
    db.payments.create_index([("provider_ref", ASCENDING)], unique=True)
    db.payments.create_index([("order_id", ASCENDING), ("estado", ASCENDING)])


@asynccontextmanager
async def lifespan(app):
    task = None
    if os.environ.get("MONGO_URL"):
        ensure_indexes(get_db())
        task = asyncio.create_task(_outbox_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="payments", docs_url=None, redoc_url=None, lifespan=lifespan)


class PaymentIn(BaseModel):
    orderId: str = Field(pattern=r"^[0-9a-f]{24}$")  # el monto NO se recibe: se obtiene de orders


class WebhookIn(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    type: Literal["payment.succeeded", "payment.failed"]
    provider_ref: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    amount: int = Field(ge=0, le=100_000_000)
    ts: int


def dto(p: dict) -> dict:
    return {"id": str(p["_id"]), "orderId": p["order_id"], "estado": p["estado"], "monto": p["monto"], "proveedor": p["proveedor"]}


def checkout_url(provider, p: dict) -> str:
    secret = provider.get("prov-webhook")["current"]
    token = signing.make_token(secret, {"ref": p["provider_ref"], "order": p["order_id"], "amount": p["monto"],
                                        "ret": f"{FRONTEND_URL}/pago.php?order={p['order_id']}"}, CHECKOUT_TTL)
    return f"{PROVIDER_PUBLIC_URL}/pay?t={token}"


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ iniciar y consultar pagos (S22, S24)
@app.post("/payments", status_code=201)
def start_payment(body: PaymentIn, p=Depends(guard(roles=ANY)), db=Depends(get_db), orders=Depends(get_orders), provider=Depends(get_provider)):
    try:
        order = orders.get_order(body.orderId)
    except ServiceDown:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    if not order or (p.role == CLIENTE and order.get("userId") != p.user_id):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")  # igual respuesta si es ajeno
    if order["estado"] != "CREADO":
        raise HTTPException(status_code=409, detail="El pedido no admite pago en su estado actual")

    pay = db.payments.find_one({"order_id": body.orderId, "estado": "PENDIENTE"})
    if not pay:  # si ya hay uno pendiente se reutiliza: iniciar dos veces no crea dos cobros
        pay = {"order_id": body.orderId, "user_id": order.get("userId"), "monto": order["total"], "estado": "PENDIENTE",
               "proveedor": "sim", "provider_ref": "sim_" + secrets.token_hex(12), "created_at": now()}
        pay["_id"] = db.payments.insert_one(pay).inserted_id
        audit("payment_started", payment=str(pay["_id"]), order=body.orderId)
    try:
        url = checkout_url(provider, pay)
    except Exception:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    return dto(pay) | {"checkoutUrl": url}


@app.get("/payments/by-orders")
def payments_by_orders(ids: str = Query(max_length=600), p=Depends(guard(roles=ANY, delegates=("graphql-gateway",))), db=Depends(get_db)):
    """Último pago de cada pedido, en una sola consulta. Un cliente solo recibe los pagos propios; los ajenos simplemente no aparecen."""
    wanted = [i for i in ids.split(",") if i]
    if not wanted or len(wanted) > 20 or not all(re.fullmatch(r"[0-9a-f]{24}", i) for i in wanted):
        raise HTTPException(status_code=400, detail="ids no válidos")
    flt: dict = {"order_id": {"$in": wanted}}
    if p.role == CLIENTE:
        flt["user_id"] = p.user_id
    out: dict = {}
    for pay in db.payments.find(flt).sort("created_at", ASCENDING):  # el más reciente pisa al anterior
        out[pay["order_id"]] = dto(pay)
    return out


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str, p=Depends(guard(roles=ANY)), db=Depends(get_db)):
    try:
        pay = db.payments.find_one({"_id": ObjectId(payment_id)})
    except (InvalidId, TypeError):
        pay = None
    if not pay or (p.role == CLIENTE and pay.get("user_id") != p.user_id):
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return dto(pay)


# ------------------------------------------------------------------ webhook del proveedor (S23)
@app.post("/webhooks/provider")
async def provider_webhook(request: Request, _=Depends(guard()), db=Depends(get_db), provider=Depends(get_provider), bus=Depends(get_bus)):
    raw = await request.body()
    try:
        keys = provider.get("prov-webhook")
    except Exception:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    if not signing.verify_bytes([keys["current"], keys["previous"]], raw, request.headers.get("x-signature", "")):
        audit("webhook_bad_signature")
        raise HTTPException(status_code=401, detail="Firma no válida")  # antes de interpretar nada del cuerpo
    try:
        ev = WebhookIn.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Evento mal formado")
    if abs(time.time() - ev.ts) > WEBHOOK_TOLERANCE:
        raise HTTPException(status_code=400, detail="Evento vencido")

    pay = db.payments.find_one({"provider_ref": ev.provider_ref})
    if not pay:
        raise HTTPException(status_code=404, detail="Pago desconocido")
    if ev.amount != pay["monto"]:
        audit("webhook_amount_mismatch", payment=str(pay["_id"]))
        raise HTTPException(status_code=422, detail="El monto no coincide")

    try:
        db.webhook_events.insert_one({"_id": ev.event_id, "ts": now()})  # índice único: un evento se procesa una sola vez
    except DuplicateKeyError:
        return {"duplicate": True}
    try:
        new = "APROBADO" if ev.type == "payment.succeeded" else "RECHAZADO"
        res = db.payments.update_one({"_id": pay["_id"], "estado": "PENDIENTE"}, {"$set": {"estado": new, "resuelto_en": now()}})
        if res.modified_count == 1 and new == "APROBADO":
            db.outbox.insert_one({"_id": f"pago-{pay['_id']}", "type": "pago.aprobado", "created_at": now(),
                                  "payload": {"order_id": pay["order_id"], "amount": pay["monto"], "provider_ref": pay["provider_ref"]}})
        elif res.modified_count != 1:
            return {"ignored": True}  # el pago ya estaba resuelto: se responde 200 para que el proveedor deje de reintentar
    except Exception:
        db.webhook_events.delete_one({"_id": ev.event_id})  # permite el reintento del proveedor
        raise
    flush_outbox(db, bus)  # mejor esfuerzo; si el broker cae, el bucle de fondo reintenta
    audit("payment_resolved", payment=str(pay["_id"]), estado=new)
    return {"estado": new}
