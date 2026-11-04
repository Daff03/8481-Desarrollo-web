"""orders: autoridad del ciclo de vida del pedido, la boleta, el despacho, las reservas de mesa y el reporte de ventas. Privado (8500).
Reglas clave: el servidor calcula nombre y precio (vía inventory); solo el evento `pago.aprobado` de payments pasa un pedido a PAGADO;
la anulación exige motivo y conserva el historial; un pedido sin pagar vence y devuelve el stock."""
import asyncio, json, logging, os, pathlib, re, threading, time, unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from shared.events import EventBus, EventBusUnavailable
from shared.service_auth import make_guard

CLIENTE, ADMIN = "cliente", "administrador"
STAFF = frozenset({"cajero", ADMIN})
ANY = frozenset({CLIENTE, "cajero", ADMIN})
PAID_STATES = ["PAGADO", "EN_PREPARACION", "LISTO", "EN_CAMINO", "ENTREGADO"]
UNPAID_TTL = timedelta(minutes=int(os.environ.get("UNPAID_TTL_MINUTES", "30")))
TZ = ZoneInfo(os.environ.get("LOCAL_TZ", "America/Santiago"))
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Estado destino → condición que debe cumplir el pedido (la transición se aplica atómicamente con este filtro).
FILTERS = {
    "PAGADO": {"estado": "CREADO"},
    "EN_PREPARACION": {"estado": "PAGADO"},
    "LISTO": {"estado": "EN_PREPARACION"},
    "EN_CAMINO": {"estado": "LISTO", "tipo": "DELIVERY"},
    "ENTREGADO": {"$or": [{"estado": "EN_CAMINO"}, {"estado": "LISTO", "tipo": "LOCAL"}]},
}
CANCEL_FROM = {"cliente": ["CREADO", "PAGADO"], "staff": ["CREADO", "PAGADO", "EN_PREPARACION"]}

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("orders")
_state: dict = {}


class StockError(Exception):
    def __init__(self, detail): self.detail = detail


class ServiceDown(Exception): ...


def get_provider():
    if "provider" not in _state:
        from shared.secret_provider import SecretProvider
        _state["provider"] = SecretProvider()
    return _state["provider"]


def get_db():
    if "db" not in _state:
        from shared import db
        _state["db"] = db.connect(get_provider(), "orders")
    return _state["db"]


class _Http:
    def __init__(self, provider, env_url, default, ref):
        self.provider, self.base, self.ref = provider, os.environ.get(env_url, default), ref

    def call(self, method, path, **kw):
        try:
            headers = {"X-Caller": "orders", "X-Caller-Key": self.provider.get(self.ref)["current"]}
            return httpx.request(method, self.base + path, headers=headers, timeout=4, **kw)
        except Exception as exc:
            raise ServiceDown() from exc


class InventoryClient(_Http):
    def __init__(self, provider): super().__init__(provider, "INVENTORY_URL", "http://svc-inventory:8400", "orders-inventory")

    def reserve(self, order_id, items):
        r = self.call("POST", "/internal/reserve", json={"orderId": order_id, "items": items})
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 409):
            raise StockError(r.json().get("detail", "No disponible"))
        raise ServiceDown()

    def release(self, order_id):
        r = self.call("POST", "/internal/release", json={"orderId": order_id})
        if r.status_code in (200, 404):  # 404: no había nada reservado
            return True
        raise ServiceDown()


class ClientsClient(_Http):
    def __init__(self, provider): super().__init__(provider, "CLIENTS_URL", "http://svc-clients:8300", "orders-clients")

    def _get(self, path):
        r = self.call("GET", path)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        raise ServiceDown()

    def by_user(self, user_id): return self._get(f"/internal/clients/by-user/{user_id}")
    def by_id(self, client_id): return self._get(f"/internal/clients/{client_id}")


def get_inventory(): return InventoryClient(get_provider())
def get_clients(): return ClientsClient(get_provider())
def get_bus(): return EventBus(get_provider(), "orders")


guard = make_guard("orders", {"gateway": "gw-orders", "payments": "orders-payments", "graphql-gateway": "gql-orders"}, get_provider)
GQL = ("graphql-gateway",)


def audit(event, **f):
    log.info(json.dumps({"ts": int(time.time()), "service": "orders", "event": event, **f}))  # sin direcciones ni contactos


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def load_coverage() -> dict:
    path = pathlib.Path(os.environ.get("COVERAGE_FILE", pathlib.Path(__file__).with_name("coverage.json")))
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"radio_km": data["radio_km"], "comunas": {norm(c) for c in data["comunas"]}}


COVERAGE = load_coverage()


# ------------------------------------------------------------------ mantenimiento en segundo plano
def release_stock(db, inv, order_id):
    try:
        inv.release(str(order_id))
        db.orders.update_one({"_id": order_id}, {"$set": {"stock_liberado": True}})
    except ServiceDown:
        audit("release_pending", order=str(order_id))  # el barrido lo reintenta


def expire_unpaid(db, inv, ttl: timedelta = UNPAID_TTL) -> int:
    """Pedidos CREADO sin pago tras `ttl`: se anulan y devuelven el stock."""
    n, cutoff = 0, now() - ttl
    while True:
        o = db.orders.find_one_and_update(
            {"estado": "CREADO", "creado_en": {"$lt": cutoff}},
            {"$set": {"estado": "CANCELADO", "motivo_anulacion": "Pago no recibido a tiempo", "cancelado_por": "sistema",
                      "cancelado_en": now(), "stock_liberado": False},
             "$push": {"historial": {"estado": "CANCELADO", "ts": now(), "actor": "sistema"}}})
        if not o:
            break
        release_stock(db, inv, o["_id"])
        audit("order_expired", order=str(o["_id"]))
        n += 1
    return n


def retry_releases(db, inv):
    for o in list(db.orders.find({"estado": "CANCELADO", "stock_liberado": False}).limit(50)):
        release_stock(db, inv, o["_id"])


def ensure_boleta(db, o):
    """Emite la boleta (número correlativo) una sola vez y encola el correo. Idempotente."""
    if o.get("boleta"):
        return
    seq = db.counters.find_one_and_update({"_id": "boleta"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)["seq"]
    res = db.orders.update_one({"_id": o["_id"], "boleta": None}, {"$set": {"boleta": {"numero": seq, "emitida_en": now(), "enviada_por_correo": False}}})
    if res.modified_count and o.get("cliente_email"):
        try:
            db.outbox.insert_one({"_id": f"boleta-{o['_id']}", "order_id": o["_id"], "type": "correo.enviar", "created_at": now(),
                                  "payload": {"to": o["cliente_email"], "template": "boleta", "data": {
                                      "numero": seq, "nombre": o["cliente_nombre"], "total": o["total"],
                                      "items": [{"cantidad": i["cantidad"], "nombre": i["nombre"], "subtotal": i["subtotal"]} for i in o["items"]]}}})
        except DuplicateKeyError:
            pass


def queue_mail(db, key, to, template, data):
    try:
        db.outbox.insert_one({"_id": key, "type": "correo.enviar", "created_at": now(), "payload": {"to": to, "template": template, "data": data}})
    except DuplicateKeyError:
        pass


def flush_outbox(db, bus) -> int:
    sent = 0
    for doc in list(db.outbox.find({}).sort("created_at", ASCENDING).limit(50)):
        try:
            bus.publish(doc["type"], doc["payload"], event_id=doc["_id"])
        except EventBusUnavailable:
            break
        db.outbox.delete_one({"_id": doc["_id"]})
        if doc.get("order_id"):
            db.orders.update_one({"_id": doc["order_id"]}, {"$set": {"boleta.enviada_por_correo": True}})
        sent += 1
    return sent


def maintenance(db, inv, bus):
    expire_unpaid(db, inv)
    retry_releases(db, inv)
    for o in list(db.orders.find({"estado": {"$in": PAID_STATES}, "boleta": None}).limit(50)):  # recuperación tras una caída
        ensure_boleta(db, o)
    flush_outbox(db, bus)


async def _maintenance_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(maintenance, get_db(), get_inventory(), get_bus())
        except Exception as exc:
            log.error(json.dumps({"event": "maintenance_failed", "error": type(exc).__name__}))


# ------------------------------------------------------------------ pago aprobado (evento de payments)
def apply_payment(db, payload: dict, event_id: str) -> str:
    """Único camino hacia PAGADO. Idempotente por event_id y por estado. Lanza ValueError si el evento es inconsistente
    (el broker lo manda a DLQ). Nunca confía en datos del navegador: viene de payments, que lo recibió firmado del proveedor."""
    try:
        db.processed_events.insert_one({"_id": event_id, "ts": now()})
    except DuplicateKeyError:
        return "duplicate"
    try:
        try:
            o = db.orders.find_one({"_id": ObjectId(payload["order_id"])})
        except (InvalidId, TypeError):
            o = None
        if not o:
            raise ValueError("Pedido inexistente")
        if int(payload["amount"]) != o["total"]:
            raise ValueError("El monto pagado no coincide con el pedido")
        if o["estado"] == "CANCELADO":  # pagó tras anular: queda marcado para reembolso
            db.orders.update_one({"_id": o["_id"]}, {"$set": {"requiere_reembolso": True, "pago_tardio": True}})
            audit("late_payment", order=str(o["_id"]))
            return "late"
        extra = {"pagado_en": now()}
        if o["tipo"] == "DELIVERY":
            extra["despacho"] = {"estado": "PENDIENTE", "conductor": None, "salida_en": None, "entregado_en": None}
        paid = move(db, o["_id"], "PAGADO", "payments", extra=extra)
        if paid is None:
            return "noop"  # ya estaba pagado
        ensure_boleta(db, paid)
        audit("order_paid", order=str(o["_id"]))
        return "paid"
    except Exception:
        db.processed_events.delete_one({"_id": event_id})  # permite que el broker reintente
        raise


def start_consumer(stop: threading.Event):
    def handler(payload, event_id):
        apply_payment(get_db(), payload, event_id)

    def loop():
        bus = get_bus()
        while not stop.is_set():
            try:
                conn = bus.consume("pago.aprobado", handler)
                while conn.is_connected() and not stop.is_set():
                    time.sleep(1)
            except Exception as exc:
                log.warning(json.dumps({"event": "broker_unavailable", "error": type(exc).__name__}))
            stop.wait(5)

    threading.Thread(target=loop, daemon=True).start()


def ensure_indexes(db):
    db.orders.create_index([("user_id", ASCENDING), ("creado_en", DESCENDING)])
    db.orders.create_index([("estado", ASCENDING), ("creado_en", ASCENDING)])
    db.orders.create_index([("client_id", ASCENDING)])
    db.reservations_mesa.create_index([("estado", ASCENDING), ("fecha_hora_dt", ASCENDING)])


_stop = threading.Event()


@asynccontextmanager
async def lifespan(app):
    task = None
    if os.environ.get("MONGO_URL"):
        ensure_indexes(get_db())
        task = asyncio.create_task(_maintenance_loop())
        if os.environ.get("START_CONSUMER", "true").lower() == "true":
            start_consumer(_stop)
    yield
    _stop.set()
    if task:
        task.cancel()


app = FastAPI(title="orders", docs_url=None, redoc_url=None, lifespan=lifespan)


# ------------------------------------------------------------------ modelos
class ItemIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=60)
    cantidad: int = Field(ge=1, le=20)


class OrderIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1, max_length=30)
    tipo: Literal["DELIVERY", "LOCAL"] = "DELIVERY"
    direccion: str | None = Field(default=None, min_length=5, max_length=120)
    comuna: str | None = Field(default=None, min_length=2, max_length=60)
    comentario: str = Field(default="", max_length=200)
    clienteId: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")  # solo lo usa el personal (venta en local)

    @model_validator(mode="after")
    def _delivery(self):
        if self.tipo == "DELIVERY" and not (self.direccion and self.comuna):
            raise ValueError("La entrega a domicilio requiere dirección y comuna")
        return self


class CancelIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=200)


class StatusIn(BaseModel):
    estado: Literal["EN_PREPARACION", "LISTO", "ENTREGADO"]


class DispatchIn(BaseModel):
    estado: Literal["EN_CAMINO", "ENTREGADO"]
    conductor: str | None = Field(default=None, min_length=2, max_length=60)


class ReservaIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=100)
    email: str = Field(max_length=254)
    personas: int = Field(ge=1, le=20)
    fechaHora: str = Field(max_length=25)
    mensaje: str = Field(default="", max_length=300)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        if len(v.split()) < 2:
            raise ValueError("Ingresa nombre y apellido")
        return " ".join(v.split())

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Correo no válido")
        return v


class ReservaStatusIn(BaseModel):
    estado: Literal["CONFIRMADA", "RECHAZADA", "CANCELADA"]


# ------------------------------------------------------------------ DTO
def dto(o: dict, staff=False) -> dict:
    d = {"id": str(o["_id"]), "estado": o["estado"], "tipo": o["tipo"], "total": o["total"], "comentario": o.get("comentario", ""),
         "direccionEntrega": o.get("direccion"), "comuna": o.get("comuna"), "motivoAnulacion": o.get("motivo_anulacion"),
         "creadoEn": iso(o["creado_en"]),
         "items": [{"productId": i["productId"], "slug": i["slug"], "nombre": i["nombre"], "precioUnitario": i["precioUnitario"],
                    "cantidad": i["cantidad"], "subtotal": i["subtotal"]} for i in o["items"]],
         "historial": [{"estado": h["estado"], "ts": iso(h["ts"])} for h in o.get("historial", [])],
         "boleta": {"numero": o["boleta"]["numero"], "emitidaEn": iso(o["boleta"]["emitida_en"])} if o.get("boleta") else None}
    if o.get("despacho"):
        s = o["despacho"]
        d["despacho"] = {"estado": s["estado"], "conductor": s.get("conductor"), "salidaEn": iso(s.get("salida_en")), "entregadoEn": iso(s.get("entregado_en"))}
    if staff:
        d["cliente"] = {"id": o["client_id"], "nombre": o["cliente_nombre"], "telefono": o.get("cliente_telefono")}
        d["requiereReembolso"] = bool(o.get("requiere_reembolso"))
    return d


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="No encontrado")


def load_order(db, order_id: str, p) -> dict:
    """Un cliente solo ve sus pedidos; si el pedido es de otro responde 404 (no revela que existe)."""
    o = db.orders.find_one({"_id": oid(order_id)})
    if not o or (p.role == CLIENTE and o.get("user_id") != p.user_id):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return o


def move(db, order_id, to: str, actor: str, *, extra: dict | None = None, extra_filter: dict | None = None):
    """Aplica una transición solo si el pedido está en un estado de origen válido. Devuelve el pedido actualizado o None."""
    flt = {"_id": order_id} | FILTERS[to] | (extra_filter or {})
    return db.orders.find_one_and_update(
        flt, {"$set": {"estado": to, **(extra or {})}, "$push": {"historial": {"estado": to, "ts": now(), "actor": actor}}},
        return_document=ReturnDocument.AFTER)


def conflict():
    return HTTPException(status_code=409, detail="El estado actual del pedido no permite esta operación")


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ cobertura (S34)
@app.get("/delivery/coverage")
def coverage(comuna: str = Query(min_length=2, max_length=60), _=Depends(guard())):
    return {"cubierta": norm(comuna) in COVERAGE["comunas"], "radioKm": COVERAGE["radio_km"]}


# ------------------------------------------------------------------ pedidos (S18–S21)
@app.post("/orders", status_code=201)
def create_order(body: OrderIn, p=Depends(guard(roles=ANY)), db=Depends(get_db), inv=Depends(get_inventory), clients=Depends(get_clients)):
    try:
        if p.role == CLIENTE:
            cl = clients.by_user(p.user_id)
        elif body.clienteId:
            cl = clients.by_id(body.clienteId)
        else:
            raise HTTPException(status_code=422, detail="Indica el cliente del pedido")
    except ServiceDown:
        raise HTTPException(status_code=503, detail="Servicio no disponible")
    if not cl:
        raise HTTPException(status_code=422, detail="Cliente no encontrado")
    if body.tipo == "DELIVERY" and norm(body.comuna) not in COVERAGE["comunas"]:
        raise HTTPException(status_code=422, detail=f"Fuera de la zona de entrega ({COVERAGE['radio_km']} km del local)")

    qty: dict[str, int] = {}
    for it in body.items:  # mismo plato repetido: se suma
        qty[it.slug] = qty.get(it.slug, 0) + it.cantidad
    if any(q > 20 for q in qty.values()):
        raise HTTPException(status_code=422, detail="Máximo 20 unidades por plato")

    order_id = ObjectId()
    try:
        res = inv.reserve(str(order_id), [{"productId": s, "cantidad": q} for s, q in qty.items()])
    except StockError as e:
        raise HTTPException(status_code=422, detail=e.detail)
    except ServiceDown:
        raise HTTPException(status_code=503, detail="Servicio no disponible")

    doc = {"_id": order_id, "estado": "CREADO", "tipo": body.tipo, "canal": "WEB" if p.role == CLIENTE else "CAJA",
           "user_id": p.user_id if p.role == CLIENTE else cl.get("userId"), "client_id": cl["id"],
           "cliente_nombre": cl["nombre"], "cliente_email": cl.get("email"), "cliente_telefono": cl.get("telefono"),
           "items": res["items"], "total": res["total"], "direccion": body.direccion if body.tipo == "DELIVERY" else None,
           "comuna": body.comuna if body.tipo == "DELIVERY" else None, "comentario": body.comentario,
           "creado_en": now(), "boleta": None, "stock_liberado": None,
           "historial": [{"estado": "CREADO", "ts": now(), "actor": p.role}]}
    try:
        db.orders.insert_one(doc)
    except Exception:
        release_stock_best_effort(inv, order_id)
        raise
    audit("order_created", order=str(order_id), canal=doc["canal"])
    return dto(doc)


def release_stock_best_effort(inv, order_id):
    try:
        inv.release(str(order_id))
    except ServiceDown:
        pass  # el barrido de inventory expira la reserva si queda a medias


@app.get("/orders")
def list_orders(estado: str | None = Query(default=None, max_length=20), page: int = Query(1, ge=1, le=1000),
                limit: int = Query(20, ge=1, le=100), p=Depends(guard(roles=ANY, delegates=GQL)), db=Depends(get_db)):
    flt: dict = {"user_id": p.user_id} if p.role == CLIENTE else {}
    if estado:
        if estado not in FILTERS and estado not in ("CREADO", "CANCELADO"):
            raise HTTPException(status_code=400, detail="Estado no válido")
        flt["estado"] = estado
    cur = db.orders.find(flt).sort("creado_en", DESCENDING).skip((page - 1) * limit).limit(limit)
    return [dto(o, staff=p.role != CLIENTE) for o in cur]


@app.get("/orders/{order_id}")
def get_order(order_id: str, p=Depends(guard(roles=ANY, delegates=GQL)), db=Depends(get_db)):
    return dto(load_order(db, order_id, p), staff=p.role != CLIENTE)


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelIn, p=Depends(guard(roles=ANY, delegates=GQL)), db=Depends(get_db), inv=Depends(get_inventory)):
    """RF3: anulación con motivo. El registro se conserva (estado CANCELADO + historial); no se borra nada."""
    o = load_order(db, order_id, p)
    allowed = CANCEL_FROM["cliente" if p.role == CLIENTE else "staff"]
    pre = db.orders.find_one_and_update(
        {"_id": o["_id"], "estado": {"$in": allowed}},
        {"$set": {"estado": "CANCELADO", "motivo_anulacion": body.motivo.strip(), "cancelado_por": p.role, "cancelado_en": now(), "stock_liberado": False},
         "$push": {"historial": {"estado": "CANCELADO", "ts": now(), "actor": p.role}}})
    if pre is None:
        raise HTTPException(status_code=409, detail="El pedido ya no puede anularse")
    if pre["estado"] != "CREADO":
        db.orders.update_one({"_id": o["_id"]}, {"$set": {"requiere_reembolso": True}})  # ya estaba pagado
    if pre.get("despacho"):
        db.orders.update_one({"_id": o["_id"]}, {"$set": {"despacho.estado": "CANCELADO"}})
    release_stock(db, inv, o["_id"])
    audit("order_cancelled", order=order_id, by=p.role)
    return dto(db.orders.find_one({"_id": o["_id"]}), staff=p.role != CLIENTE)


@app.get("/orders/{order_id}/receipt")
def receipt(order_id: str, p=Depends(guard(roles=ANY)), db=Depends(get_db)):
    o = load_order(db, order_id, p)
    if not o.get("boleta"):
        raise HTTPException(status_code=404, detail="La boleta se emite al confirmarse el pago")
    return {"numero": o["boleta"]["numero"], "emitidaEn": iso(o["boleta"]["emitida_en"]), "pedido": str(o["_id"]),
            "cliente": o["cliente_nombre"], "items": [{"nombre": i["nombre"], "cantidad": i["cantidad"], "precioUnitario": i["precioUnitario"],
                                                       "subtotal": i["subtotal"]} for i in o["items"]], "total": o["total"]}


# ------------------------------------------------------------------ cocina y despacho (S27–S29)
@app.patch("/orders/{order_id}/status")
def set_status(order_id: str, body: StatusIn, p=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    """Cocina: EN_PREPARACION y LISTO. ENTREGADO aquí solo para pedidos en local; los de delivery se entregan desde /dispatch."""
    flt = {"tipo": "LOCAL"} if body.estado == "ENTREGADO" else None
    o = move(db, oid(order_id), body.estado, p.role, extra_filter=flt)
    if o is None:
        if not db.orders.find_one({"_id": oid(order_id)}):
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        raise conflict()
    audit("order_status", order=order_id, estado=body.estado)
    return dto(o, staff=True)


@app.get("/dispatch")
def dispatch_board(estado: str = Query(default="LISTO", max_length=20), page: int = Query(1, ge=1, le=1000), limit: int = Query(50, ge=1, le=100),
                   p=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    if estado not in PAID_STATES:
        raise HTTPException(status_code=400, detail="Estado no válido")
    cur = db.orders.find({"tipo": "DELIVERY", "estado": estado}).sort("creado_en", ASCENDING).skip((page - 1) * limit).limit(limit)
    return [dto(o, staff=True) for o in cur]


@app.patch("/dispatch/{order_id}")
def dispatch(order_id: str, body: DispatchIn, p=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    o = db.orders.find_one({"_id": oid(order_id), "tipo": "DELIVERY"})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    d = o.get("despacho") or {}
    if body.estado == "EN_CAMINO":
        conductor = body.conductor or d.get("conductor")
        if not conductor:
            raise HTTPException(status_code=422, detail="Asigna un conductor")
        extra = {"despacho.estado": "EN_CAMINO", "despacho.conductor": conductor, "despacho.salida_en": now()}
    else:
        extra = {"despacho.estado": "ENTREGADO", "despacho.entregado_en": now()}
    upd = move(db, o["_id"], body.estado, p.role, extra=extra)
    if upd is None:
        raise conflict()
    audit("order_dispatch", order=order_id, estado=body.estado)
    return dto(upd, staff=True)


# ------------------------------------------------------------------ uso interno de payments
@app.get("/internal/orders/{order_id}")
def internal_order(order_id: str, _=Depends(guard(services=("payments",), gateway=False)), db=Depends(get_db)):
    """payments consulta el monto y el estado reales; jamás usa un monto del navegador."""
    o = db.orders.find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return {"id": str(o["_id"]), "estado": o["estado"], "total": o["total"], "userId": o.get("user_id"), "clienteId": o["client_id"]}


# ------------------------------------------------------------------ reservas de mesa (RF14: S30–S32)
def parse_reserva_fecha(text: str) -> datetime:
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha no válida")
    if dt.tzinfo:
        dt = dt.astimezone(TZ).replace(tzinfo=None)
    local_now = datetime.now(TZ).replace(tzinfo=None)
    if not local_now < dt <= local_now + timedelta(days=90):
        raise HTTPException(status_code=422, detail="La fecha debe ser futura (hasta 90 días)")
    return dt.replace(second=0, microsecond=0)


def reserva_dto(r: dict) -> dict:
    return {"id": str(r["_id"]), "estado": r["estado"], "nombre": r["nombre"], "email": r["email"], "personas": r["personas"],
            "fechaHora": r["fecha_hora_dt"].isoformat(timespec="minutes"), "mensaje": r.get("mensaje", ""), "creadoEn": iso(r["creado_en"])}


@app.post("/reservations", status_code=201)
def create_reservation(body: ReservaIn, p=Depends(guard()), db=Depends(get_db)):
    dt = parse_reserva_fecha(body.fechaHora)
    doc = {"estado": "PENDIENTE", "nombre": body.nombre, "email": body.email, "personas": body.personas, "fecha_hora_dt": dt,
           "mensaje": body.mensaje, "user_id": p.user_id, "creado_en": now()}
    doc["_id"] = db.reservations_mesa.insert_one(doc).inserted_id
    queue_mail(db, f"reserva-{doc['_id']}-PENDIENTE", body.email, "reserva",
               {"estado": "PENDIENTE", "nombre": body.nombre, "personas": body.personas, "fechaHora": dt.isoformat(timespec="minutes")})
    audit("reservation_created", reservation=str(doc["_id"]))
    return {"id": str(doc["_id"]), "estado": "PENDIENTE"}


@app.get("/reservations")
def list_reservations(estado: str | None = Query(default=None, max_length=12), page: int = Query(1, ge=1, le=1000),
                      limit: int = Query(50, ge=1, le=100), _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    flt = {}
    if estado:
        if estado not in ("PENDIENTE", "CONFIRMADA", "RECHAZADA", "CANCELADA"):
            raise HTTPException(status_code=400, detail="Estado no válido")
        flt["estado"] = estado
    cur = db.reservations_mesa.find(flt).sort("fecha_hora_dt", ASCENDING).skip((page - 1) * limit).limit(limit)
    return [reserva_dto(r) for r in cur]


@app.patch("/reservations/{rid}")
def set_reservation(rid: str, body: ReservaStatusIn, _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    origin = ["PENDIENTE"] if body.estado in ("CONFIRMADA", "RECHAZADA") else ["PENDIENTE", "CONFIRMADA"]
    r = db.reservations_mesa.find_one_and_update({"_id": oid(rid), "estado": {"$in": origin}}, {"$set": {"estado": body.estado}},
                                                 return_document=ReturnDocument.AFTER)
    if r is None:
        if not db.reservations_mesa.find_one({"_id": oid(rid)}):
            raise HTTPException(status_code=404, detail="Reserva no encontrada")
        raise conflict()
    queue_mail(db, f"reserva-{rid}-{body.estado}", r["email"], "reserva",
               {"estado": body.estado, "nombre": r["nombre"], "personas": r["personas"], "fechaHora": r["fecha_hora_dt"].isoformat(timespec="minutes")})
    return reserva_dto(r)


# ------------------------------------------------------------------ reporte de ventas (RF9, S26)
@app.get("/reports/sales")
def sales_report(desde: date | None = None, hasta: date | None = None, _=Depends(guard(roles=frozenset({ADMIN}))), db=Depends(get_db)):
    """Ventas = pedidos pagados (no anulados) cuyo pago cayó dentro del rango. Se agrega aquí, en el servicio dueño de los datos."""
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=30)
    if desde > hasta or (hasta - desde).days > 366:
        raise HTTPException(status_code=400, detail="Rango no válido (máximo 366 días)")
    def utc(d: date):  # medianoche local → UTC naive (así se guardan las fechas)
        return datetime.combine(d, datetime.min.time(), tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)
    start, end = utc(desde), utc(hasta + timedelta(days=1))
    por_dia: dict[str, dict] = {}
    por_plato: dict[str, dict] = {}
    por_tipo: dict[str, dict] = {}
    total = pedidos = 0
    for o in db.orders.find({"estado": {"$in": PAID_STATES}, "pagado_en": {"$gte": start, "$lt": end}}, {"total": 1, "pagado_en": 1, "tipo": 1, "items": 1}):
        total += o["total"]; pedidos += 1
        dia = o["pagado_en"].replace(tzinfo=timezone.utc).astimezone(TZ).date().isoformat()
        d = por_dia.setdefault(dia, {"pedidos": 0, "total": 0})
        d["pedidos"] += 1; d["total"] += o["total"]
        t = por_tipo.setdefault(o["tipo"], {"pedidos": 0, "total": 0})
        t["pedidos"] += 1; t["total"] += o["total"]
        for i in o["items"]:
            pl = por_plato.setdefault(i["slug"], {"nombre": i["nombre"], "unidades": 0, "total": 0})
            pl["unidades"] += i["cantidad"]; pl["total"] += i["subtotal"]
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "pedidos": pedidos, "total": total,
            "ticketPromedio": total // pedidos if pedidos else 0,
            "porDia": [{"fecha": k, **v} for k, v in sorted(por_dia.items())],
            "porTipo": [{"tipo": k, **v} for k, v in sorted(por_tipo.items())],
            "topPlatos": sorted(({"slug": k, **v} for k, v in por_plato.items()), key=lambda x: -x["unidades"])[:10]}
