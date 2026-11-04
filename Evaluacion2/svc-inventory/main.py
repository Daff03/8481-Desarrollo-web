"""inventory: autoridad del catálogo, la disponibilidad, el stock y las promociones. Privado (8400).
Es el único que escribe en inventory_db. orders lo usa para reservar stock de forma atómica y obtener
nombre y precio calculados en el servidor (el navegador nunca fija precios)."""
import asyncio, json, logging, os, re, time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from shared.service_auth import make_guard

CATEGORIAS = {"entradas", "carnes", "vegetarianos", "postres"}
ADMIN, STAFF = frozenset({"administrador"}), frozenset({"cajero", "administrador"})
MAX_QTY, MAX_ITEMS = 20, 30
ID_RE = re.compile(r"^[0-9a-f]{24}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("inventory")
_state: dict = {}


def get_provider():
    if "provider" not in _state:
        from shared.secret_provider import SecretProvider
        _state["provider"] = SecretProvider()
    return _state["provider"]


def get_db():
    if "db" not in _state:
        from shared import db
        _state["db"] = db.connect(get_provider(), "inventory")
    return _state["db"]


guard = make_guard("inventory", {"gateway": "gw-inventory", "orders": "orders-inventory", "graphql-gateway": "gql-inventory"}, get_provider)


def audit(event, **f):
    log.info(json.dumps({"ts": int(time.time()), "service": "inventory", "event": event, **f}))


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@asynccontextmanager
async def lifespan(app):
    if os.environ.get("MONGO_URL"):
        db = get_db()
        ensure_indexes(db)
        if os.environ.get("SEED_ON_START", "false").lower() == "true" and db.products.count_documents({}) == 0:
            import seed
            seed.seed(db)
        task = asyncio.create_task(_sweeper(db))
        yield
        task.cancel()
        return
    yield


app = FastAPI(title="inventory", docs_url=None, redoc_url=None, lifespan=lifespan)


def ensure_indexes(db):
    db.products.create_index([("slug", ASCENDING)], unique=True)
    db.products.create_index([("categoria", ASCENDING), ("activo", ASCENDING)])


# ------------------------------------------------------------------ DTO (lo que sale al exterior)
def public(p: dict) -> dict:
    """Solo campos de catálogo. No se expone stock, activo ni fechas internas."""
    return {"id": str(p["_id"]), "slug": p["slug"], "nombre": p["nombre"], "categoria": p["categoria"], "precio": p["precio"],
            "disponible": bool(p["activo"] and p["disponible"] and p["stock"] > 0),
            "descripcion": p.get("descripcion", ""), "imagen": p.get("imagen"), "popular": p.get("popular", False)}


def staff_view(p: dict) -> dict:
    return public(p) | {"stock": p["stock"], "activo": p["activo"]}


class ProductIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=60)
    nombre: str = Field(min_length=2, max_length=80)
    categoria: str
    precio: int = Field(ge=1, le=1_000_000)
    descripcion: str = Field(default="", max_length=500)
    imagen: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9/_.-]{1,120}$")
    stock: int = Field(default=0, ge=0, le=100_000)
    disponible: bool = True
    popular: bool = False


class AvailabilityIn(BaseModel):
    disponible: bool
    stock: int | None = Field(default=None, ge=0, le=100_000)


class Line(BaseModel):
    productId: str = Field(pattern=r"^([0-9a-f]{24}|[a-z0-9]+(-[a-z0-9]+)*)$", max_length=60)  # id o slug
    cantidad: int = Field(ge=1, le=MAX_QTY)


class ReserveIn(BaseModel):
    orderId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    items: list[Line] = Field(min_length=1, max_length=MAX_ITEMS)


class ReleaseIn(BaseModel):
    orderId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


def find(db, ident: str, include_inactive=False):
    q = {"_id": ObjectId(ident)} if ID_RE.match(ident) else {"slug": ident}
    if not include_inactive:
        q["activo"] = True
    p = db.products.find_one(q)
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return p


def check_category(c):
    if c not in CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoría no válida")


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ catálogo público (S01, S02, S35)
@app.get("/products")
def list_products(available: str | None = None, categoria: str | None = None, slugs: str | None = Query(default=None, max_length=1900),
                  page: int = Query(1, ge=1, le=1000), limit: int = Query(50, ge=1, le=100),
                  _=Depends(guard(delegates=("graphql-gateway",))), db=Depends(get_db)):
    q: dict = {"activo": True}
    if available is not None:
        if available not in ("true", "false"):
            raise HTTPException(status_code=400, detail="available debe ser true o false")
        q["disponible"] = True
        q["stock"] = {"$gt": 0}
        if available == "false":
            q = {"activo": True, "$or": [{"disponible": False}, {"stock": {"$lte": 0}}]}
    if categoria is not None:
        check_category(categoria)
        q["categoria"] = categoria
    if slugs is not None:  # consulta por lote (batching): hasta MAX_ITEMS platos en una sola llamada
        wanted = [s for s in slugs.split(",") if s]
        if not wanted or len(wanted) > MAX_ITEMS or not all(SLUG_RE.match(s) for s in wanted):
            raise HTTPException(status_code=400, detail="slugs no válidos")
        q["slug"] = {"$in": wanted}
    cur = db.products.find(q).sort([("categoria", ASCENDING), ("nombre", ASCENDING)]).skip((page - 1) * limit).limit(limit)
    return [public(p) for p in cur]


@app.get("/products/{ident}")
def get_product(ident: str, _=Depends(guard()), db=Depends(get_db)):
    return public(find(db, ident))


@app.get("/promotions")
def list_promotions(_=Depends(guard()), db=Depends(get_db)):
    today = date.today().isoformat()
    return [{"id": str(x["_id"]), "titulo": x["titulo"], "descuentoPct": x["descuentoPct"], "vigenciaDesde": x["vigenciaDesde"],
             "vigenciaHasta": x["vigenciaHasta"], "productIds": [str(i) for i in x["productIds"]]}
            for x in db.promotions.find({"vigenciaDesde": {"$lte": today}, "vigenciaHasta": {"$gte": today}})]


# ------------------------------------------------------------------ mantenedor (S14–S17, S40)
@app.get("/admin/products")
def admin_list(categoria: str | None = None, page: int = Query(1, ge=1, le=1000), limit: int = Query(50, ge=1, le=100),
               _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    """Vista de personal: incluye platos dados de baja, stock y estado. No es público."""
    q: dict = {}
    if categoria is not None:
        check_category(categoria)
        q["categoria"] = categoria
    cur = db.products.find(q).sort([("categoria", ASCENDING), ("nombre", ASCENDING)]).skip((page - 1) * limit).limit(limit)
    return [staff_view(p) for p in cur]



@app.post("/products", status_code=201)
def create_product(body: ProductIn, _=Depends(guard(roles=ADMIN)), db=Depends(get_db)):
    check_category(body.categoria)
    doc = body.model_dump() | {"activo": True, "created_at": now(), "updated_at": now()}
    try:
        doc["_id"] = db.products.insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un producto con ese slug")
    audit("product_created", product=str(doc["_id"]))
    return staff_view(doc)


@app.put("/products/{ident}")
def replace_product(ident: str, body: ProductIn, _=Depends(guard(roles=ADMIN)), db=Depends(get_db)):
    check_category(body.categoria)
    p = find(db, ident)
    try:
        db.products.update_one({"_id": p["_id"]}, {"$set": body.model_dump() | {"updated_at": now()}})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Ya existe un producto con ese slug")
    audit("product_replaced", product=str(p["_id"]))
    return staff_view(db.products.find_one({"_id": p["_id"]}))


@app.patch("/products/{ident}/availability")
def set_availability(ident: str, body: AvailabilityIn, _=Depends(guard(roles=STAFF)), db=Depends(get_db)):
    p = find(db, ident)
    upd = {"disponible": body.disponible, "updated_at": now()}
    if body.stock is not None:
        upd["stock"] = body.stock
    db.products.update_one({"_id": p["_id"]}, {"$set": upd})
    audit("availability_changed", product=str(p["_id"]), disponible=body.disponible)
    return staff_view(db.products.find_one({"_id": p["_id"]}))


@app.delete("/products/{ident}", status_code=204)
def delete_product(ident: str, _=Depends(guard(roles=ADMIN)), db=Depends(get_db)):
    """Baja lógica: el historial de pedidos conserva su copia de nombre y precio."""
    p = find(db, ident, include_inactive=True)
    db.products.update_one({"_id": p["_id"]}, {"$set": {"activo": False, "updated_at": now()}})
    audit("product_deactivated", product=str(p["_id"]))


# ------------------------------------------------------------------ uso interno de orders
def effective_price(db, product: dict) -> int:
    today = date.today().isoformat()
    pct = max([x["descuentoPct"] for x in db.promotions.find(
        {"productIds": product["_id"], "vigenciaDesde": {"$lte": today}, "vigenciaHasta": {"$gte": today}})] or [0])
    return (product["precio"] * (100 - pct) + 50) // 100


@app.post("/internal/reserve")
def reserve(body: ReserveIn, _=Depends(guard(services=("orders",), gateway=False)), db=Depends(get_db)):
    """Reserva stock de todo el pedido o de nada. Idempotente por orderId. Cada descuento es atómico en Mongo:
    el filtro con $gte y el $inc ocurren en una sola operación, así dos pedidos simultáneos no pueden vender la misma unidad."""
    # productId acepta el id o el slug (el frontend usa slug); se resuelve antes de tocar el stock
    resolved = []
    for it in body.items:
        try:
            resolved.append((it, find(db, it.productId)))
        except HTTPException:
            raise HTTPException(status_code=409, detail="Producto no disponible")
    ids = [p["_id"] for _, p in resolved]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Producto repetido en el pedido")

    try:
        db.reservations.insert_one({"_id": body.orderId, "state": "pending", "created_at": now(), "restock": []})
    except DuplicateKeyError:
        prev = db.reservations.find_one({"_id": body.orderId})
        if prev and prev["state"] == "reserved":
            return prev["result"]
        raise HTTPException(status_code=409, detail="La reserva de este pedido está en curso o ya fue cerrada")

    done: list[tuple[ObjectId, int]] = []  # lo ya descontado y registrado en la reserva (el barrido lo puede deshacer)
    lines = []
    try:
        for it, p in resolved:
            if not p["disponible"]:
                raise _Unavailable(it.productId, "Producto no disponible")
            res = db.products.update_one({"_id": p["_id"], "activo": True, "disponible": True, "stock": {"$gte": it.cantidad}},
                                         {"$inc": {"stock": -it.cantidad}})
            if res.modified_count != 1:
                raise _Unavailable(it.productId, "Sin stock suficiente")
            # Se anota el descuento de inmediato: si el proceso muere aquí, el barrido sabe cuánto devolver.
            logged = db.reservations.update_one({"_id": body.orderId, "state": "pending"},
                                                {"$push": {"restock": [str(p["_id"]), it.cantidad]}})
            if logged.modified_count != 1:  # el barrido expiró esta reserva mientras trabajábamos
                _rollback(db, [(p["_id"], it.cantidad)])
                raise _Expired()
            done.append((p["_id"], it.cantidad))
            price = effective_price(db, p)
            lines.append({"productId": str(p["_id"]), "slug": p["slug"], "nombre": p["nombre"], "precioUnitario": price,
                          "cantidad": it.cantidad, "subtotal": price * it.cantidad})
    except _Unavailable as e:
        db.reservations.update_one({"_id": body.orderId, "state": "pending"}, {"$set": {"state": "rejected"}})
        _rollback(db, done)
        db.reservations.delete_one({"_id": body.orderId, "state": "rejected"})  # permite reintentar con otro carrito
        audit("reserve_rejected", order=body.orderId, product=e.product_id)
        raise HTTPException(status_code=409, detail=e.detail)
    except _Expired:
        raise HTTPException(status_code=409, detail="La reserva expiró; vuelve a intentarlo")
    except Exception:
        db.reservations.update_one({"_id": body.orderId, "state": "pending"}, {"$set": {"state": "rejected"}})
        _rollback(db, done)
        db.reservations.delete_one({"_id": body.orderId, "state": "rejected"})
        raise

    result = {"orderId": body.orderId, "items": lines, "total": sum(l["subtotal"] for l in lines)}
    ok = db.reservations.update_one({"_id": body.orderId, "state": "pending"}, {"$set": {"state": "reserved", "result": result}})
    if ok.modified_count != 1:  # expirada justo antes de cerrar: el barrido ya devolvió el stock
        raise HTTPException(status_code=409, detail="La reserva expiró; vuelve a intentarlo")
    audit("reserved", order=body.orderId, items=len(lines))
    return result


STALE_AFTER = timedelta(minutes=int(os.environ.get("RESERVATION_STALE_MINUTES", "2")))


def sweep_stale(db, older_than: timedelta = STALE_AFTER) -> int:
    """Reservas que quedaron 'pending' (el proceso murió a mitad): se marcan 'expired' y se devuelve lo ya descontado.
    La reserva expirada se conserva para que un proceso lento no pueda reanudarla ni duplicar la devolución."""
    cutoff, n = now() - older_than, 0
    while True:
        r = db.reservations.find_one_and_update({"state": "pending", "created_at": {"$lt": cutoff}}, {"$set": {"state": "expired"}})
        if not r:
            return n
        _rollback(db, [(ObjectId(o), q) for o, q in r.get("restock", [])])
        audit("reservation_expired", order=r["_id"])
        n += 1


async def _sweeper(db):
    while True:
        try:
            await asyncio.to_thread(sweep_stale, db)
        except Exception as exc:  # no tumbar el servicio por un fallo del barrido
            log.error(json.dumps({"event": "sweep_failed", "error": type(exc).__name__}))
        await asyncio.sleep(60)


@app.post("/internal/release")
def release(body: ReleaseIn, _=Depends(guard(services=("orders",), gateway=False)), db=Depends(get_db)):
    """Devuelve el stock de un pedido anulado. Idempotente: liberar dos veces no suma dos veces."""
    claimed = db.reservations.find_one_and_update({"_id": body.orderId, "state": "reserved"}, {"$set": {"state": "released"}})
    if claimed:
        _rollback(db, [(ObjectId(o), q) for o, q in claimed["restock"]])
        audit("released", order=body.orderId)
        return {"orderId": body.orderId, "released": True}
    prev = db.reservations.find_one({"_id": body.orderId})
    if prev and prev["state"] == "released":
        return {"orderId": body.orderId, "released": True}
    raise HTTPException(status_code=404, detail="Reserva no encontrada")


class _Expired(Exception):
    pass


class _Unavailable(Exception):
    def __init__(self, product_id, detail):
        self.product_id, self.detail = product_id, detail


def _rollback(db, done):
    for oid, qty in done:
        db.products.update_one({"_id": oid}, {"$inc": {"stock": qty}})
