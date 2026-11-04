"""API Gateway: único punto público (puerto 8000). Aplica lista blanca de rutas y verbos, sesión por cookie
HttpOnly, roles, defensa CSRF por Origin, límite de solicitudes y timeouts; descarta toda cabecera de identidad
del navegador y reenvía solo una identidad interna firmada de 30 s. Los servicios vuelven a comprobar propiedad y reglas."""
import json, logging, os, re, time, uuid
from collections import defaultdict, deque

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from routes import ROUTES, Route

try:
    from shared import internal_jwt
except ImportError:  # ejecución local desde gateway/ sin el paquete en el path
    import pathlib, sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from shared import internal_jwt

API_PREFIX = "/api/v1"
MAX_BODY = 1_000_000
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
# destino → (variable con la URL, URL por defecto en la red privada, referencia de credencial, audiencia del JWT)
TARGETS = {
    "auth":      ("AUTH_URL",      "http://auth:8100",            "gw-auth",      "auth"),
    "clients":   ("CLIENTS_URL",   "http://svc-clients:8300",     "gw-clients",   "clients"),
    "inventory": ("INVENTORY_URL", "http://svc-inventory:8400",   "gw-inventory", "inventory"),
    "orders":    ("ORDERS_URL",    "http://svc-orders:8500",      "gw-orders",    "orders"),
    "payments":  ("PAYMENTS_URL",  "http://svc-payments:8600",    "gw-payments",  "payments"),
    "graphql":   ("GRAPHQL_URL",   "http://graphql-gateway:8700", "gw-graphql",   "graphql-gateway"),
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("gateway")


class GatewayError(Exception):
    def __init__(self, status: int, detail: str, headers: dict | None = None):
        self.status, self.detail, self.headers = status, detail, headers or {}


class RateLimiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0):
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise GatewayError(429, "Demasiadas solicitudes", {"Retry-After": str(int(window - (now - q[0])) + 1)})
        q.append(now)
        if len(self.hits) > 10_000:  # evita crecimiento sin límite
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > window]:
                self.hits.pop(k, None)


def compile_routes(routes: list[Route]):
    out = []
    for r in routes:
        rx = re.sub(r"\{(\w+)\}", lambda m: f"(?P<{m.group(1)}>[A-Za-z0-9_-]{{1,64}})", r.path)
        out.append((re.compile(f"^{rx}$"), r))
    return out


def env_settings():
    return {
        "origins": [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8080").split(",") if o.strip()],
        "cookie": os.environ.get("COOKIE_NAME", "alsahara_session"),
        "secure": os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        "rate": int(os.environ.get("RATE_LIMIT_PER_MIN", "120")),
        "login_rate": int(os.environ.get("LOGIN_RATE_PER_MIN", "10")),
        "timeout": float(os.environ.get("UPSTREAM_TIMEOUT", "5")),
        "urls": {t: os.environ.get(v[0], v[1]) for t, v in TARGETS.items()},
    }


def create_app(provider=None, client: httpx.AsyncClient | None = None, settings: dict | None = None) -> FastAPI:
    cfg = settings or env_settings()
    table = compile_routes(ROUTES)
    limiter = RateLimiter()
    state = {"provider": provider, "client": client}

    def get_provider():
        if state["provider"] is None:
            from shared.secret_provider import SecretProvider
            state["provider"] = SecretProvider()
        return state["provider"]

    async def secret(ref: str) -> dict:
        try:
            return await run_in_threadpool(get_provider().get, ref)
        except Exception:  # gestor de secretos caído y caché vencida: falla cerrado
            raise GatewayError(503, "Servicio no disponible")

    async def http() -> httpx.AsyncClient:
        if state["client"] is None:
            state["client"] = httpx.AsyncClient(timeout=cfg["timeout"], follow_redirects=False)
        return state["client"]

    app = FastAPI(title="gateway", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=cfg["origins"], allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"], max_age=600)

    # ------------------------------------------------------------------ utilidades
    def guard(request: Request, route_key: str, *, unsafe: bool, exempt_origin: bool = False, limit: int | None = None):
        ip = request.client.host if request.client else "?"
        limiter.check(f"{ip}:{route_key}", limit or cfg["rate"])
        if unsafe and not exempt_origin:
            # CSRF: la cookie viaja sola, así que una escritura solo vale si nace de un origen permitido.
            if request.headers.get("origin") not in cfg["origins"]:
                raise GatewayError(403, "Origen no permitido")

    async def read_body(request: Request) -> bytes:
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            raise GatewayError(413, "Solicitud demasiado grande")
        body = await request.body()
        if len(body) > MAX_BODY:
            raise GatewayError(413, "Solicitud demasiado grande")
        if body and not request.headers.get("content-type", "").lower().startswith("application/json"):
            raise GatewayError(415, "Se espera application/json")
        return body

    async def call(target: str, method: str, dest: str, cid: str, *, body: bytes = b"", params=None, identity: dict | None = None,
                   extra: dict | None = None):
        _, _, key_ref, aud = TARGETS[target]
        key = (await secret(key_ref))["current"]
        headers = {"X-Caller": "gateway", "X-Caller-Key": key, "X-Correlation-Id": cid, "Accept": "application/json"}
        headers.update(extra or {})  # solo las cabeceras que la ruta declara; nunca identidad
        if body:
            headers["Content-Type"] = "application/json"
        if identity:
            jwt_key = (await secret("internal-jwt"))["current"]
            headers["X-Internal-Identity"] = internal_jwt.sign(jwt_key, identity["user_id"], identity["role"], aud, cid)
        try:
            c = await http()
            return await c.request(method, cfg["urls"][target] + dest, headers=headers, content=body or None, params=params)
        except httpx.TimeoutException:
            raise GatewayError(504, "El servicio tardó demasiado")
        except httpx.HTTPError:
            raise GatewayError(503, "Servicio no disponible")

    async def session_identity(request: Request, cid: str) -> dict | None:
        token = request.cookies.get(cfg["cookie"])
        if not token:
            return None
        r = await call("auth", "POST", "/session/verify", cid, body=json.dumps({"token": token}).encode())
        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            return None
        raise GatewayError(503, "Servicio no disponible")

    def relay(r: httpx.Response, cid: str, private: bool) -> Response:
        if r.status_code >= 500:
            raise GatewayError(502, "Error en el servicio")
        resp = Response(content=r.content, status_code=r.status_code)
        if r.headers.get("content-type"):
            resp.headers["content-type"] = r.headers["content-type"]
        if private:
            resp.headers["cache-control"] = "no-store"
        return resp  # no se reenvían Set-Cookie ni otras cabeceras del interior

    def finish(resp: Response, cid: str) -> Response:
        resp.headers["X-Correlation-Id"] = cid
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    def fail(e: GatewayError, cid: str) -> Response:
        return finish(JSONResponse({"detail": e.detail, "correlation_id": cid}, status_code=e.status, headers=e.headers), cid)

    def record(cid, method, route, status, started, role=None):
        log.info(json.dumps({"ts": int(time.time()), "cid": cid, "method": method, "route": route, "status": status,
                             "ms": int((time.monotonic() - started) * 1000), "role": role}))

    def set_session_cookie(resp: Response, token: str, max_age: int):
        resp.set_cookie(cfg["cookie"], token, max_age=max_age, httponly=True, secure=cfg["secure"], samesite="lax", path="/")

    # ------------------------------------------------------------------ rutas propias (sesión)
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post(API_PREFIX + "/auth/login")
    async def login(request: Request):
        cid, t0 = uuid.uuid4().hex[:16], time.monotonic()
        try:
            guard(request, "login", unsafe=True, limit=cfg["login_rate"])
            body = await read_body(request)
            r = await call("auth", "POST", "/login", cid, body=body)
            if r.status_code != 200:
                resp = relay(r, cid, True)
            else:
                data = r.json()  # el token solo viaja en la cookie HttpOnly, nunca en el cuerpo
                resp = JSONResponse({"role": data["role"], "user_id": data["user_id"]}, headers={"cache-control": "no-store"})
                set_session_cookie(resp, data["token"], data["expires_in"])
            record(cid, "POST", "/auth/login", resp.status_code, t0)
            return finish(resp, cid)
        except GatewayError as e:
            record(cid, "POST", "/auth/login", e.status, t0)
            return fail(e, cid)

    @app.post(API_PREFIX + "/auth/logout")
    async def logout(request: Request):
        cid, t0 = uuid.uuid4().hex[:16], time.monotonic()
        try:
            guard(request, "logout", unsafe=True)
            token = request.cookies.get(cfg["cookie"])
            if token:
                try:
                    await call("auth", "POST", "/logout", cid, body=json.dumps({"token": token}).encode())
                except GatewayError:
                    pass  # igual se borra la cookie; la sesión vence sola
            resp = Response(status_code=204)
            resp.delete_cookie(cfg["cookie"], path="/", httponly=True, secure=cfg["secure"], samesite="lax")
            record(cid, "POST", "/auth/logout", 204, t0)
            return finish(resp, cid)
        except GatewayError as e:
            record(cid, "POST", "/auth/logout", e.status, t0)
            return fail(e, cid)

    @app.get(API_PREFIX + "/auth/session")
    async def session(request: Request):
        cid, t0 = uuid.uuid4().hex[:16], time.monotonic()
        try:
            guard(request, "session", unsafe=False)
            ident = await session_identity(request, cid)
            resp = JSONResponse({"authenticated": bool(ident), "role": ident["role"] if ident else None},
                                headers={"cache-control": "no-store"})
            record(cid, "GET", "/auth/session", 200, t0, ident["role"] if ident else None)
            return finish(resp, cid)
        except GatewayError as e:
            record(cid, "GET", "/auth/session", e.status, t0)
            return fail(e, cid)

    # ------------------------------------------------------------------ proxy con lista blanca
    @app.api_route(API_PREFIX + "/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def proxy(request: Request, rest: str):
        cid, t0 = uuid.uuid4().hex[:16], time.monotonic()
        path, method = "/" + rest, request.method
        route_label, role = path, None
        try:
            matches = [(m, r) for rx, r in table if (m := rx.match(path))]
            if not matches:
                raise GatewayError(404, "No encontrado")
            hit = next(((m, r) for m, r in matches if r.method == method), None)
            if hit is None:
                raise GatewayError(405, "Método no permitido", {"Allow": ", ".join(sorted({r.method for _, r in matches}))})
            m, route = hit
            route_label = route.path

            guard(request, route.path, unsafe=method in UNSAFE, exempt_origin=route.path.startswith("/webhooks/"))

            extra = set(request.query_params.keys()) - set(route.query)
            if extra:
                raise GatewayError(400, "Parámetros no admitidos")
            params = list(request.query_params.multi_items())
            if len(request.url.query) > 512:
                raise GatewayError(400, "Consulta demasiado larga")

            body = await read_body(request)

            identity = None
            if route.access != "anon" or route.roles:
                identity = await session_identity(request, cid)
                if identity is None and route.access == "user":
                    raise GatewayError(401, "Sesión no válida")
                if route.roles and (identity is None or identity["role"] not in route.roles):
                    raise GatewayError(403, "Sin permiso")
                role = identity["role"] if identity else None

            dest = route.dest.format(**m.groupdict())
            extra = {h: request.headers[h][:256] for h in route.headers if h in request.headers}
            r = await call(route.target, method, dest, cid, body=body, params=params, identity=identity, extra=extra)
            resp = relay(r, cid, private=identity is not None)
            record(cid, method, route_label, resp.status_code, t0, role)
            return finish(resp, cid)
        except GatewayError as e:
            record(cid, method, route_label, e.status, t0, role)
            return fail(e, cid)

    return app


app = create_app()
