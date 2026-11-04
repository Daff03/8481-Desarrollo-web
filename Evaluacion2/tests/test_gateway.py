import importlib.util, json, pathlib, sys
import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "gateway"))
from shared import internal_jwt

ORIGIN = {"Origin": "http://localhost:8080"}
SESSIONS = {"tok-ana": {"user_id": "u-ana", "role": "cliente"}, "tok-admin": {"user_id": "u-admin", "role": "administrador"}}


class FakeProvider:
    def __init__(self): self.down = False
    def get(self, ref):
        if self.down: raise RuntimeError("gestor caído")
        return {"current": f"valor-{ref}", "previous": None}


class Upstream:
    """Simula los servicios privados y guarda lo que el gateway les envía."""
    def __init__(self): self.calls, self.mode = [], "ok"

    def handler(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        self.calls.append((req.url.host, req.method, req.url.path, dict(req.headers), body, req.url.params))
        if self.mode == "timeout": raise httpx.ReadTimeout("t", request=req)
        if self.mode == "down" and req.url.host != "auth": raise httpx.ConnectError("x", request=req)
        if req.url.path == "/session/verify":
            s = SESSIONS.get(body["token"])
            return httpx.Response(200, json=s) if s else httpx.Response(401, json={"detail": "no"})
        if req.url.path == "/login":
            if body.get("email") == "ana@correo.cl":
                return httpx.Response(200, json={"token": "tok-ana", "expires_in": 100, "role": "cliente", "user_id": "u-ana"})
            return httpx.Response(401, json={"detail": "Credenciales inválidas"})
        if self.mode == "boom": return httpx.Response(500, text="Traceback secreto en el servicio")
        return httpx.Response(200, json={"ok": True}, headers={"Set-Cookie": "interno=1"})

    def to(self, host):  # llamadas a un servicio, sin las de verificación de sesión
        return [c for c in self.calls if c[0] == host and c[2] != "/session/verify"]


@pytest.fixture()
def ctx():
    spec = importlib.util.spec_from_file_location("gateway_main", ROOT / "gateway" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    up, prov = Upstream(), FakeProvider()
    settings = mod.env_settings() | {"rate": 1000, "login_rate": 1000}
    app = mod.create_app(provider=prov, client=httpx.AsyncClient(transport=httpx.MockTransport(up.handler)), settings=settings)
    yield TestClient(app), up, prov, mod, settings


def ck(tok): return {"Cookie": f"alsahara_session={tok}"}


# ---- las 6 validaciones de la guía, a nivel de gateway ----
def test_1_catalogo_anonimo(ctx):
    c, up, *_ = ctx
    r = c.get("/api/v1/products?available=true")
    assert r.status_code == 200 and r.json() == {"ok": True}
    host, method, path, headers, _, params = up.to("svc-inventory")[0]
    assert (method, path, params["available"]) == ("GET", "/products", "true")
    assert "x-internal-identity" not in headers  # anónimo: sin identidad
    assert "set-cookie" not in r.headers          # el interior no puede fijar cookies


def test_2_operacion_protegida_sin_sesion_401(ctx):
    c, up, *_ = ctx
    assert c.get("/api/v1/orders").status_code == 401
    assert c.get("/api/v1/orders", headers=ck("token-falso")).status_code == 401
    assert up.to("svc-orders") == []


def test_3_administracion_con_rol_cliente_403(ctx):
    c, up, *_ = ctx
    r = c.delete("/api/v1/products/abc", headers=ORIGIN | ck("tok-ana"))
    assert r.status_code == 403 and up.to("svc-inventory") == []
    assert c.delete("/api/v1/products/abc", headers=ORIGIN | ck("tok-admin")).status_code == 200


def test_vista_admin_del_catalogo_solo_personal(ctx):
    c, up, *_ = ctx
    assert c.get("/api/v1/admin/products").status_code == 401
    assert c.get("/api/v1/admin/products", headers=ck("tok-ana")).status_code == 403
    assert c.get("/api/v1/admin/products?categoria=postres", headers=ck("tok-admin")).status_code == 200
    assert up.to("svc-inventory")[0][2] == "/admin/products"


def test_4_identidad_que_llega_al_servicio_es_la_verificada(ctx):
    c, up, *_ = ctx
    falsas = {"X-User-Id": "u-admin", "X-Role": "administrador", "X-Internal-Identity": "forjado", "Authorization": "Bearer x"}
    assert c.get("/api/v1/orders/abc123", headers=falsas | ck("tok-ana")).status_code == 200
    h = up.to("svc-orders")[0][3]
    assert "x-user-id" not in h and "x-role" not in h and "authorization" not in h and "cookie" not in h
    claims = internal_jwt.verify(h["x-internal-identity"], ["valor-internal-jwt"], "orders")
    assert claims["sub"] == "u-ana" and claims["role"] == "cliente" and claims["exp"] - claims["iat"] <= 30
    with pytest.raises(internal_jwt.InvalidIdentity):  # un token para orders no sirve en payments
        internal_jwt.verify(h["x-internal-identity"], ["valor-internal-jwt"], "payments")


def test_5_acceso_directo_sin_identidad_rechazado_por_el_token(ctx):
    # Lo que un servicio exigiría si alguien lo llamara sin pasar por el gateway: firma válida y destino correcto.
    token = internal_jwt.sign("otra-clave", "u-x", "administrador", "orders", "cid")
    with pytest.raises(internal_jwt.InvalidIdentity):
        internal_jwt.verify(token, ["valor-internal-jwt"], "orders")
    vencido = internal_jwt.sign("valor-internal-jwt", "u-x", "cliente", "orders", "cid", ttl=-5)
    with pytest.raises(internal_jwt.InvalidIdentity):
        internal_jwt.verify(vencido, ["valor-internal-jwt"], "orders")


def test_6_pago_alterado_no_cambia_el_estado_desde_el_gateway(ctx):
    c, up, *_ = ctx
    # No existe ruta para marcar un pedido como PAGADO: solo el webhook del proveedor llega a payments.
    assert c.patch("/api/v1/orders/abc/status", headers=ORIGIN, json={"estado": "PAGADO"}).status_code == 401
    r = c.patch("/api/v1/orders/abc/status", headers=ORIGIN | ck("tok-ana"), json={"estado": "PAGADO"})
    assert r.status_code == 403 and up.to("svc-orders") == []


# ---- lista blanca, CSRF, límites y fallos ----
def test_ruta_no_listada_404_y_verbo_no_listado_405(ctx):
    c, *_ = ctx
    assert c.get("/api/v1/internal/health").status_code == 404
    assert c.get("/api/v1/secrets/gw-orders").status_code == 404
    assert c.get("/api/v1/products/..%2fsecrets").status_code == 404
    r = c.put("/api/v1/products", headers=ORIGIN | ck("tok-admin"), json={})
    assert r.status_code == 405 and "POST" in r.headers["allow"]
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404


def test_csrf_escritura_exige_origen_permitido(ctx):
    c, up, *_ = ctx
    body = {"productId": "x", "cantidad": 1}
    assert c.post("/api/v1/orders", json=body, headers=ck("tok-ana")).status_code == 403
    assert c.post("/api/v1/orders", json=body, headers={"Origin": "http://evil.com"} | ck("tok-ana")).status_code == 403
    assert up.to("svc-orders") == []
    assert c.post("/api/v1/orders", json=body, headers=ORIGIN | ck("tok-ana")).status_code == 200


def test_webhook_no_exige_origen_y_reenvia_solo_la_firma(ctx):
    c, up, *_ = ctx
    r = c.post("/api/v1/webhooks/payments", json={"event_id": "e1"}, headers={"X-Signature": "sha256=abc", "X-User-Id": "u-admin"})
    assert r.status_code == 200
    host, method, path, h, body, _ = up.to("svc-payments")[0]
    assert path == "/webhooks/provider" and h["x-signature"] == "sha256=abc" and "x-user-id" not in h and "x-internal-identity" not in h


def test_consulta_con_parametros_no_admitidos_400(ctx):
    c, up, *_ = ctx
    assert c.get("/api/v1/products?available=true&$where=1").status_code == 400
    assert up.to("svc-inventory") == []


def test_login_fija_cookie_httponly_y_no_expone_token(ctx):
    c, *_ = ctx
    r = c.post("/api/v1/auth/login", headers=ORIGIN, json={"email": "ana@correo.cl", "password": "x"})
    assert r.status_code == 200 and "tok-ana" not in r.text and r.json()["role"] == "cliente"
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc and "alsahara_session=tok-ana" in sc
    bad = c.post("/api/v1/auth/login", headers=ORIGIN, json={"email": "otro@correo.cl", "password": "x"})
    assert bad.status_code == 401 and "set-cookie" not in bad.headers


def test_logout_revoca_y_borra_cookie(ctx):
    c, up, *_ = ctx
    r = c.post("/api/v1/auth/logout", headers=ORIGIN | ck("tok-ana"))
    assert r.status_code == 204 and "max-age=0" in r.headers["set-cookie"].lower()
    assert any(p == "/logout" for _, _, p, *_ in up.calls)


def test_session_informa_estado(ctx):
    c, *_ = ctx
    assert c.get("/api/v1/auth/session").json() == {"authenticated": False, "role": None}
    assert c.get("/api/v1/auth/session", headers=ck("tok-admin")).json() == {"authenticated": True, "role": "administrador"}


def test_cors_con_credenciales_solo_origen_permitido(ctx):
    c, *_ = ctx
    ok = c.get("/api/v1/products", headers=ORIGIN)
    assert ok.headers["access-control-allow-origin"] == "http://localhost:8080" and ok.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in c.get("/api/v1/products", headers={"Origin": "http://evil.com"}).headers


def test_limite_de_solicitudes_429(ctx):
    c, up, prov, mod, settings = ctx
    app = mod.create_app(provider=prov, client=httpx.AsyncClient(transport=httpx.MockTransport(up.handler)),
                         settings=settings | {"rate": 3})
    t = TestClient(app)
    assert [t.get("/api/v1/products").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert "retry-after" in t.get("/api/v1/products").headers


def test_errores_controlados_sin_detalles_internos(ctx):
    c, up, *_ = ctx
    up.mode = "boom"
    r = c.get("/api/v1/products")
    assert r.status_code == 502 and "Traceback" not in r.text
    up.mode = "timeout"
    assert c.get("/api/v1/products").status_code == 504
    up.mode = "down"
    assert c.get("/api/v1/products").status_code == 503


def test_gestor_de_secretos_caido_falla_cerrado(ctx):
    c, up, prov, *_ = ctx
    prov.down = True
    assert c.get("/api/v1/products").status_code == 503 and up.calls == []


def test_cuerpo_grande_o_no_json_rechazado(ctx):
    c, *_ = ctx
    assert c.post("/api/v1/orders", headers=ORIGIN | ck("tok-ana"), content=b"x" * 2_000_000,
                  ).status_code in (413, 415)
    assert c.post("/api/v1/orders", headers=ORIGIN | ck("tok-ana") | {"Content-Type": "text/plain"}, content=b"hola").status_code == 415


def test_jwt_interno_acepta_emisor_graphql_y_rechaza_otros():
    ok = internal_jwt.sign("k", "u1", "cliente", "orders", "cid", issuer="graphql-gateway")
    assert internal_jwt.verify(ok, ["k"], "orders")["sub"] == "u1"
    with pytest.raises(internal_jwt.InvalidIdentity):
        internal_jwt.verify(internal_jwt.sign("k", "u1", "cliente", "orders", "cid", issuer="otro-servicio"), ["k"], "orders")
