"""GraphQL Gateway privado (8700). Lo llama solo el API Gateway, con la identidad del usuario ya verificada.
Compone lecturas de orders + inventory + payments en una sola consulta, sin acceder jamás a sus bases de datos:
para cada servicio destino re-emite la identidad del usuario (JWT de 30 s con ese destino) y usa su propia credencial de tramo,
de modo que la propiedad de los recursos la sigue decidiendo el servicio dueño. Aplica autorización por campo, límites de
profundidad y costo, paginación acotada, batching (una llamada por lote, no por ítem), plazo máximo y errores parciales."""
import asyncio, inspect, json, logging, os, pathlib, re, time, uuid

import httpx
from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from graphql import GraphQLError, GraphQLSyntaxError, build_schema, execute, parse, specified_rules, validate
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import limits
from shared import internal_jwt
from shared.service_auth import make_guard

STAFF = {"cajero", "administrador"}
ANY = frozenset({"cliente", "cajero", "administrador"})
HEX24 = re.compile(r"^[0-9a-f]{24}$")
MAX_PAGE_SIZE = 20
# destino → (variable con la URL, URL por defecto, referencia de la credencial del tramo, audiencia del JWT)
TARGETS = {
    "orders": ("ORDERS_URL", "http://svc-orders:8500", "gql-orders", "orders"),
    "inventory": ("INVENTORY_URL", "http://svc-inventory:8400", "gql-inventory", "inventory"),
    "payments": ("PAYMENTS_URL", "http://svc-payments:8600", "gql-payments", "payments"),
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("graphql-gateway")


class AppError(GraphQLError):
    """Error controlado y seguro de mostrar al cliente. Cualquier otra excepción se oculta como 'Error interno'."""
    def __init__(self, message: str, code: str):
        super().__init__(message, extensions={"code": code})


class Loader:
    """Agrupa las peticiones del mismo instante en una sola llamada (batching) y recuerda los resultados durante la consulta."""
    def __init__(self, batch_fn, max_batch=20):
        self.batch_fn, self.max_batch, self.cache, self.queue = batch_fn, max_batch, {}, []

    def load(self, key):
        if key in self.cache:
            return self.cache[key]
        fut = asyncio.get_running_loop().create_future()
        self.cache[key] = fut
        self.queue.append(key)
        if len(self.queue) == 1:
            asyncio.get_running_loop().create_task(self._dispatch())
        return fut

    async def _dispatch(self):
        await asyncio.sleep(0)  # deja que los demás resolvers hermanos encolen su clave
        keys, self.queue = self.queue, []
        for i in range(0, len(keys), self.max_batch):
            chunk = keys[i:i + self.max_batch]
            try:
                found = await self.batch_fn(chunk)
                for k in chunk:
                    self.cache[k].set_result(found.get(k))
            except Exception as exc:  # falla solo el campo que dependía del lote (error parcial)
                for k in chunk:
                    if not self.cache[k].done():
                        self.cache[k].set_exception(exc)
                        self.cache[k].exception()  # marca la excepción como consultada


class Upstream:
    """Llamadas a un servicio destino con credencial de tramo + identidad del usuario re-emitida."""
    def __init__(self, provider, http, urls, principal, cid):
        self.provider, self.http, self.urls, self.p, self.cid = provider, http, urls, principal, cid

    async def call(self, target, method, path, *, params=None, body=None):
        _, _, key_ref, aud = TARGETS[target]
        try:
            key = (await run_in_threadpool(self.provider.get, key_ref))["current"]
            jwt_key = (await run_in_threadpool(self.provider.get, "internal-jwt"))["current"]
        except Exception:
            raise AppError(f"El servicio de {target} no está disponible", "UPSTREAM_UNAVAILABLE")
        headers = {"X-Caller": "graphql-gateway", "X-Caller-Key": key, "X-Correlation-Id": self.cid, "Accept": "application/json",
                   "X-Internal-Identity": internal_jwt.sign(jwt_key, self.p.user_id, self.p.role, aud, self.cid, issuer="graphql-gateway")}
        try:
            r = await self.http.request(method, self.urls[target] + path, headers=headers, params=params, json=body)
        except httpx.TimeoutException:
            raise AppError(f"El servicio de {target} tardó demasiado", "UPSTREAM_TIMEOUT")
        except httpx.HTTPError:
            raise AppError(f"El servicio de {target} no está disponible", "UPSTREAM_UNAVAILABLE")
        if r.status_code >= 500:
            raise AppError(f"El servicio de {target} no está disponible", "UPSTREAM_UNAVAILABLE")
        if r.status_code in (401, 403):
            raise AppError("No autorizado", "FORBIDDEN")
        return r


class Ctx:
    def __init__(self, upstream, principal):
        self.up, self.p = upstream, principal
        self.products = Loader(self._products)
        self.payments = Loader(self._payments)

    async def _products(self, slugs):
        r = await self.up.call("inventory", "GET", "/products", params={"slugs": ",".join(slugs)})
        return {p["slug"]: p for p in r.json()} if r.status_code == 200 else {}

    async def _payments(self, order_ids):
        r = await self.up.call("payments", "GET", "/payments/by-orders", params={"ids": ",".join(order_ids)})
        return r.json() if r.status_code == 200 else {}


# ------------------------------------------------------------------ resolvers
def _check_id(value):
    if not HEX24.match(value or ""):
        raise AppError("Identificador no válido", "BAD_REQUEST")


async def resolve_resumen(_, info, id):
    _check_id(id)
    r = await info.context.up.call("orders", "GET", f"/orders/{id}")
    return r.json() if r.status_code == 200 else None   # 404: no existe o no es tuyo → null, sin revelar cuál


async def resolve_mis_pedidos(_, info, page=1, limit=10):
    if not (1 <= limit <= MAX_PAGE_SIZE and 1 <= page <= 1000):
        raise AppError(f"limit entre 1 y {MAX_PAGE_SIZE}", "BAD_REQUEST")
    r = await info.context.up.call("orders", "GET", "/orders", params={"page": page, "limit": limit})
    if r.status_code != 200:
        raise AppError("No se pudieron obtener los pedidos", "UPSTREAM_UNAVAILABLE")
    return r.json()


async def resolve_anular(_, info, id, motivo):
    _check_id(id)
    r = await info.context.up.call("orders", "POST", f"/orders/{id}/cancel", body={"motivo": motivo})
    if r.status_code == 200:
        return r.json()
    raise {404: AppError("Pedido no encontrado", "NOT_FOUND"), 409: AppError("El pedido ya no puede anularse", "CONFLICT"),
           422: AppError("Motivo no válido (mínimo 5 caracteres)", "BAD_REQUEST")}.get(r.status_code, AppError("No se pudo anular", "UPSTREAM_UNAVAILABLE"))


def staff_only(field):
    """Autorización por campo: aunque orders ya no lo entrega a un cliente, aquí se vuelve a exigir."""
    def resolve(order, info):
        if info.context.p.role not in STAFF:
            raise AppError("No autorizado para ver este campo", "FORBIDDEN")
        return order.get(field)
    return resolve


def resolve_producto(item, info):
    return info.context.products.load(item["slug"])


def resolve_pago(order, info):
    return info.context.payments.load(order["id"])


def build():
    schema = build_schema((pathlib.Path(__file__).with_name("schema.graphql")).read_text(encoding="utf-8"))
    schema.query_type.fields["resumenPedido"].resolve = resolve_resumen
    schema.query_type.fields["misPedidos"].resolve = resolve_mis_pedidos
    schema.mutation_type.fields["anularPedido"].resolve = resolve_anular
    pedido, item = schema.type_map["ResumenPedido"].fields, schema.type_map["ItemPedido"].fields
    pedido["cliente"].resolve = staff_only("cliente")
    pedido["requiereReembolso"].resolve = staff_only("requiereReembolso")
    pedido["pago"].resolve = resolve_pago
    item["producto"].resolve = resolve_producto
    return schema


# ------------------------------------------------------------------ aplicación
class GqlIn(BaseModel):
    query: str = Field(max_length=5000)
    variables: dict | None = None
    operationName: str | None = Field(default=None, max_length=64)


def format_error(e: GraphQLError) -> dict:
    out = {"message": e.message, "path": e.path}
    code = (e.extensions or {}).get("code")
    if code:
        out["extensions"] = {"code": code}
    elif e.original_error is not None:  # excepción inesperada: no se filtran detalles internos
        log.error(json.dumps({"event": "resolver_error", "type": type(e.original_error).__name__}))
        out.update(message="Error interno", extensions={"code": "INTERNAL"})
    return out


def create_app(provider=None, client: httpx.AsyncClient | None = None, settings: dict | None = None) -> FastAPI:
    cfg = {"max_depth": int(os.environ.get("GQL_MAX_DEPTH", "6")), "max_cost": int(os.environ.get("GQL_MAX_COST", "1000")),
           "max_root": int(os.environ.get("GQL_MAX_ROOT_FIELDS", "5")), "timeout": float(os.environ.get("GQL_TIMEOUT", "8")),
           "upstream_timeout": float(os.environ.get("UPSTREAM_TIMEOUT", "3")),
           "introspection": os.environ.get("GRAPHQL_INTROSPECTION", "false").lower() == "true",
           "urls": {t: os.environ.get(v[0], v[1]) for t, v in TARGETS.items()}} | (settings or {})
    state = {"provider": provider, "client": client}
    schema = build()

    def get_provider():
        if state["provider"] is None:
            from shared.secret_provider import SecretProvider
            state["provider"] = SecretProvider()
        return state["provider"]

    guard = make_guard("graphql-gateway", {"gateway": "gw-graphql"}, get_provider)
    app = FastAPI(title="graphql-gateway", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def reject(message, code, status=400):
        return JSONResponse({"errors": [{"message": message, "extensions": {"code": code}}]}, status_code=status)

    @app.post("/graphql")
    async def graphql_endpoint(body: GqlIn, p=Depends(guard(roles=ANY)), x_correlation_id: str | None = Header(default=None)):
        cid, t0 = (x_correlation_id or uuid.uuid4().hex)[:32], time.monotonic()
        try:
            document = parse(body.query)
        except GraphQLSyntaxError as e:
            return reject(e.message, "SYNTAX_ERROR")
        errors = validate(schema, document, rules=specified_rules)
        if errors:
            return JSONResponse({"errors": [{"message": e.message, "extensions": {"code": "VALIDATION_ERROR"}} for e in errors]}, status_code=400)
        try:
            limits.check(document, body.operationName, max_depth=cfg["max_depth"], max_cost=cfg["max_cost"],
                         max_root_fields=cfg["max_root"], allow_introspection=cfg["introspection"])
        except limits.QueryRejected as e:
            log.info(json.dumps({"cid": cid, "event": "query_rejected", "code": e.code}))
            return reject(e.message, e.code)

        if state["client"] is None:
            state["client"] = httpx.AsyncClient(timeout=cfg["upstream_timeout"])
        ctx = Ctx(Upstream(get_provider(), state["client"], cfg["urls"], p, cid), p)
        try:
            result = execute(schema, document, context_value=ctx, variable_values=body.variables, operation_name=body.operationName)
            if inspect.isawaitable(result):
                result = await asyncio.wait_for(result, cfg["timeout"])
        except asyncio.TimeoutError:
            return reject("La consulta superó el plazo máximo", "TIMEOUT", 504)
        payload = {"data": result.data}
        if result.errors:
            payload["errors"] = [format_error(e) for e in result.errors]
        log.info(json.dumps({"cid": cid, "event": "graphql", "role": p.role, "ms": int((time.monotonic() - t0) * 1000), "errors": len(result.errors or [])}))
        return payload

    return app


app = create_app()
