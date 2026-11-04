import importlib.util, json, pathlib, sys, time
from urllib.parse import parse_qs, urlparse
import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import internal_jwt, signing
from shared.events import EventBusUnavailable

GW = {"X-Caller": "gateway", "X-Caller-Key": "valor-gw-payments"}
SECRET = "valor-prov-webhook"
OID = "b" * 24


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def as_(role, uid="user-1"):
    return GW | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", uid, role, "payments", "cid")}


class FakeProvider:
    def __init__(self): self.prev = {}
    def get(self, ref): return {"current": f"valor-{ref}", "previous": self.prev.get(ref)}


class FakeBus:
    def __init__(self): self.sent, self.down = [], False
    def publish(self, t, payload, event_id=None, correlation_id=None):
        if self.down: raise EventBusUnavailable()
        self.sent.append((t, payload, event_id))


class FakeOrders:
    def __init__(self, mod): self.mod, self.down = mod, False
    order = {"id": OID, "estado": "CREADO", "total": 27980, "userId": "user-1", "clienteId": "c"}
    def get_order(self, oid):
        if self.down: raise self.mod.ServiceDown()
        return dict(self.order) if oid == OID else None


@pytest.fixture()
def ctx():
    mod = load("payments_main", "svc-payments/main.py")
    db = mongomock.MongoClient()["payments_db"]
    mod.ensure_indexes(db)
    orders, bus, prov = FakeOrders(mod), FakeBus(), FakeProvider()
    app = mod.app
    app.dependency_overrides.update({mod.get_db: lambda: db, mod.get_provider: lambda: prov, mod.get_orders: lambda: orders, mod.get_bus: lambda: bus})
    with TestClient(app) as c:
        yield c, db, orders, bus, prov, mod


def iniciar(c, uid="user-1", role="cliente", **extra):
    return c.post("/payments", headers=as_(role, uid), json={"orderId": OID} | extra)


def webhook(c, event=None, secret=SECRET, sig=None, **over):
    ev = {"event_id": "evt-" + str(time.time_ns()), "type": "payment.succeeded", "provider_ref": "", "amount": 27980, "ts": int(time.time())} | (event or {}) | over
    raw = json.dumps(ev).encode()
    return c.post("/webhooks/provider", content=raw, headers=GW | {"X-Signature": sig or "sha256=" + signing.sign_bytes(secret, raw), "Content-Type": "application/json"}), ev


def ref_de(db): return db.payments.find_one({})["provider_ref"]


# ------------------------------------------------------------------ iniciar pago
def test_el_monto_sale_de_orders_no_del_navegador(ctx):
    c, db, *_ = ctx
    r = iniciar(c, monto=1, amount=1, estado="APROBADO")
    assert r.status_code == 201 and r.json()["monto"] == 27980 and r.json()["estado"] == "PENDIENTE"
    pay = db.payments.find_one({})
    assert pay["monto"] == 27980 and pay["user_id"] == "user-1" and pay["provider_ref"].startswith("sim_")
    url = urlparse(r.json()["checkoutUrl"])
    claims = signing.read_token([SECRET], parse_qs(url.query)["t"][0])
    assert claims["amount"] == 27980 and claims["order"] == OID and claims["ref"] == pay["provider_ref"]


def test_pago_de_pedido_ajeno_o_inexistente_404(ctx):
    c, db, orders, *_ = ctx
    assert iniciar(c, uid="intruso").status_code == 404
    assert c.post("/payments", headers=as_("cliente"), json={"orderId": "0" * 24}).status_code == 404
    assert c.post("/payments", headers=as_("cliente"), json={"orderId": "xx"}).status_code == 422
    assert c.post("/payments", headers=GW, json={"orderId": OID}).status_code == 401
    assert iniciar(c, uid="staff", role="cajero").status_code == 201      # el personal cobra en caja
    assert db.payments.count_documents({}) == 1


def test_pedido_que_no_esta_creado_no_se_cobra(ctx):
    c, db, orders, *_ = ctx
    for estado in ("PAGADO", "CANCELADO", "ENTREGADO"):
        orders.order = orders.order | {"estado": estado}
        assert iniciar(c).status_code == 409
    assert db.payments.count_documents({}) == 0


def test_iniciar_dos_veces_reutiliza_el_cobro(ctx):
    c, db, *_ = ctx
    a, b = iniciar(c).json(), iniciar(c).json()
    assert a["id"] == b["id"] and db.payments.count_documents({}) == 1


def test_orders_caido_503(ctx):
    c, db, orders, *_ = ctx
    orders.down = True
    assert iniciar(c).status_code == 503 and db.payments.count_documents({}) == 0


def test_consulta_de_pago_solo_dueno_o_personal(ctx):
    c, *_ = ctx
    pid = iniciar(c).json()["id"]
    assert c.get(f"/payments/{pid}", headers=as_("cliente")).json()["monto"] == 27980
    assert c.get(f"/payments/{pid}", headers=as_("cliente", "intruso")).status_code == 404
    assert c.get(f"/payments/{pid}", headers=as_("cajero", "s")).status_code == 200
    assert c.get("/payments/no-id", headers=as_("cliente")).status_code == 404


# ------------------------------------------------------------------ webhook: firma, idempotencia, monto
def test_webhook_aprobado_publica_un_solo_evento(ctx):
    c, db, _, bus, *_ = ctx
    iniciar(c)
    r, ev = webhook(c, provider_ref=ref_de(db))
    assert r.status_code == 200 and r.json() == {"estado": "APROBADO"} and db.payments.find_one({})["estado"] == "APROBADO"
    t, payload, event_id = bus.sent[0]
    assert t == "pago.aprobado" and payload == {"order_id": OID, "amount": 27980, "provider_ref": ref_de(db)}
    assert event_id == f"pago-{db.payments.find_one({})['_id']}" and db.outbox.count_documents({}) == 0


def test_webhook_repetido_no_procesa_dos_veces(ctx):
    c, db, _, bus, *_ = ctx
    iniciar(c)
    raw = json.dumps({"event_id": "evt-fijo-1", "type": "payment.succeeded", "provider_ref": ref_de(db), "amount": 27980, "ts": int(time.time())}).encode()
    h = GW | {"X-Signature": "sha256=" + signing.sign_bytes(SECRET, raw), "Content-Type": "application/json"}
    assert c.post("/webhooks/provider", content=raw, headers=h).json() == {"estado": "APROBADO"}
    assert c.post("/webhooks/provider", content=raw, headers=h).json() == {"duplicate": True}
    r2, _ = webhook(c, provider_ref=ref_de(db))                    # otro evento del mismo pago
    assert r2.json() == {"ignored": True} and len(bus.sent) == 1


def test_firma_invalida_o_ausente_401_y_no_cambia_nada(ctx):
    c, db, _, bus, *_ = ctx
    iniciar(c)
    ref = ref_de(db)
    assert webhook(c, provider_ref=ref, secret="otra-clave")[0].status_code == 401
    assert webhook(c, provider_ref=ref, sig="sha256=" + "0" * 64)[0].status_code == 401
    assert c.post("/webhooks/provider", json={"provider_ref": ref}, headers=GW).status_code == 401
    raw = json.dumps({"event_id": "evt-x-123", "type": "payment.succeeded", "provider_ref": ref, "amount": 27980, "ts": int(time.time())}).encode()
    firma = "sha256=" + signing.sign_bytes(SECRET, raw)
    alterado = raw.replace(b"27980", b"1")                          # alteran el monto después de firmar
    assert c.post("/webhooks/provider", content=alterado, headers=GW | {"X-Signature": firma}).status_code == 401
    assert db.payments.find_one({})["estado"] == "PENDIENTE" and bus.sent == [] and db.webhook_events.count_documents({}) == 0


def test_monto_distinto_al_del_pago_se_rechaza(ctx):
    c, db, _, bus, *_ = ctx
    iniciar(c)
    r, _ = webhook(c, provider_ref=ref_de(db), amount=1000)        # firma válida pero monto alterado
    assert r.status_code == 422 and db.payments.find_one({})["estado"] == "PENDIENTE" and bus.sent == []


def test_evento_vencido_o_mal_formado_o_desconocido(ctx):
    c, db, *_ = ctx
    iniciar(c)
    ref = ref_de(db)
    assert webhook(c, provider_ref=ref, ts=int(time.time()) - 3600)[0].status_code == 400     # repetición antigua
    assert webhook(c, provider_ref=ref, type="payment.refunded")[0].status_code == 400
    assert webhook(c, provider_ref="sim_inexistente")[0].status_code == 404
    assert db.payments.find_one({})["estado"] == "PENDIENTE"


def test_pago_rechazado_permite_reintentar(ctx):
    c, db, _, bus, *_ = ctx
    iniciar(c)
    assert webhook(c, provider_ref=ref_de(db), type="payment.failed")[0].json() == {"estado": "RECHAZADO"} and bus.sent == []
    assert webhook(c, provider_ref=ref_de(db))[0].json() == {"ignored": True}     # un "éxito" posterior no revive el pago
    assert iniciar(c).status_code == 201 and db.payments.count_documents({}) == 2


def test_acepta_la_clave_anterior_tras_rotar(ctx):
    c, db, _, _, prov, _ = ctx
    iniciar(c)
    prov.prev["prov-webhook"] = "clave-vieja"
    assert webhook(c, provider_ref=ref_de(db), secret="clave-vieja")[0].status_code == 200


def test_broker_caido_conserva_el_aviso_y_lo_reintenta(ctx):
    c, db, _, bus, _, mod = ctx
    iniciar(c)
    bus.down = True
    assert webhook(c, provider_ref=ref_de(db))[0].status_code == 200
    assert db.payments.find_one({})["estado"] == "APROBADO" and db.outbox.count_documents({}) == 1 and bus.sent == []
    bus.down = False
    assert mod.flush_outbox(db, bus) == 1 and mod.flush_outbox(db, bus) == 0 and len(bus.sent) == 1


# ------------------------------------------------------------------ recorrido completo: proveedor → payments → evento → orders
def test_del_proveedor_simulado_al_pedido_pagado(ctx, monkeypatch):
    c, db, orders, bus, _, _ = ctx
    sim = load("provider_main", "provider-sim/main.py")
    sim.WEBHOOK_SECRET, sim.FRONTEND_URL = SECRET, "http://localhost:8080"
    url = iniciar(c).json()["checkoutUrl"]
    token = parse_qs(urlparse(url).query)["t"][0]
    s = TestClient(sim.app)

    assert "$27.980" in s.get(f"/pay?t={token}").text and s.get("/pay?t=falso").status_code == 400
    enviados = []
    monkeypatch.setattr(sim.httpx, "post", lambda u, content, headers, timeout: enviados.append((u, content, headers)) or None)
    r = s.post("/pay/result", content=f"t={token}&resultado=ok", headers={"Content-Type": "application/x-www-form-urlencoded"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"http://localhost:8080/pago.php?order={OID}&estado=ok")
    u, raw, headers = enviados[0]
    assert u.endswith("/api/v1/webhooks/payments")

    # lo que el proveedor firmó es exactamente lo que payments acepta
    assert c.post("/webhooks/provider", content=raw, headers=GW | {"X-Signature": headers["X-Signature"]}).json() == {"estado": "APROBADO"}

    # y el evento publicado es lo que orders consume para pasar a PAGADO
    orders_mod = load("orders_main_e2e", "svc-orders/main.py")
    odb = mongomock.MongoClient()["orders_db"]
    odb.orders.insert_one({"_id": ObjectId(OID), "estado": "CREADO", "tipo": "LOCAL", "total": 27980, "items": [], "cliente_email": None,
                           "cliente_nombre": "Ana", "historial": [], "boleta": None})
    _, payload, event_id = bus.sent[0]
    assert orders_mod.apply_payment(odb, payload, event_id) == "paid"
    assert odb.orders.find_one({})["estado"] == "PAGADO" and orders_mod.apply_payment(odb, payload, event_id) == "duplicate"


def test_proveedor_simulado_rechaza_enlaces_manipulados(ctx):
    sim = load("provider_main2", "provider-sim/main.py")
    sim.WEBHOOK_SECRET = SECRET
    s = TestClient(sim.app)
    bueno = signing.make_token(SECRET, {"ref": "sim_x", "order": OID, "amount": 100, "ret": "http://evil.com/robo?a=1"}, 60)
    malo = signing.make_token("otra", {"ref": "sim_x", "order": OID, "amount": 100, "ret": "x"}, 60)
    vencido = signing.make_token(SECRET, {"ref": "sim_x", "order": OID, "amount": 100, "ret": "x"}, -5)
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    for t in (malo, vencido):
        assert s.post("/pay/result", content=f"t={t}&resultado=ok", headers=form).status_code == 400
    assert s.post("/pay/result", content=f"t={bueno}&resultado=hackeo", headers=form).status_code == 400
    assert s.get("/docs").status_code == 404


GQL = {"X-Caller": "graphql-gateway", "X-Caller-Key": "valor-gql-payments"}


def pago(db, order, user, estado="APROBADO", segundos=0):
    from datetime import datetime, timedelta
    db.payments.insert_one({"order_id": order, "user_id": user, "monto": 100, "estado": estado, "proveedor": "sim",
                            "provider_ref": f"sim_{order[:4]}{estado[:3]}{segundos}", "created_at": datetime.utcnow() + timedelta(seconds=segundos)})


def test_pagos_por_lote_respetan_la_propiedad(ctx):
    c, db, *_ = ctx
    a, b = "a" * 24, "b" * 24
    pago(db, a, "user-1"); pago(db, b, "user-2")
    mios = c.get(f"/payments/by-orders?ids={a},{b}", headers=as_("cliente", "user-1")).json()
    assert list(mios) == [a] and mios[a]["estado"] == "APROBADO" and "provider_ref" not in str(mios)
    assert sorted(c.get(f"/payments/by-orders?ids={a},{b}", headers=as_("cajero", "s")).json()) == [a, b]
    assert c.get(f"/payments/by-orders?ids={b}", headers=as_("cliente", "user-1")).json() == {}


def test_pagos_por_lote_devuelve_el_mas_reciente_y_valida_ids(ctx):
    c, db, *_ = ctx
    a = "a" * 24
    pago(db, a, "user-1", "RECHAZADO", 0); pago(db, a, "user-1", "APROBADO", 10)
    assert c.get(f"/payments/by-orders?ids={a}", headers=as_("cliente", "user-1")).json()[a]["estado"] == "APROBADO"
    for malo in ("", "xx", ",".join(["a" * 24] * 21), "a" * 24 + ";x"):
        assert c.get(f"/payments/by-orders?ids={malo}", headers=as_("cliente", "user-1")).status_code in (400, 422), malo
    assert c.get(f"/payments/by-orders?ids={a}", headers=GW).status_code == 401


def test_graphql_gateway_puede_leer_pagos_con_identidad_pero_no_iniciarlos(ctx):
    c, db, *_ = ctx
    a = "a" * 24
    pago(db, a, "user-1")
    ident = {"X-Internal-Identity": as_("cliente", "user-1")["X-Internal-Identity"]}
    assert c.get(f"/payments/by-orders?ids={a}", headers=GQL | ident).status_code == 200
    assert c.get(f"/payments/by-orders?ids={a}", headers=GQL).status_code == 401              # sin identidad de usuario
    assert c.post("/payments", headers=GQL | ident, json={"orderId": OID}).status_code == 403
    assert c.post("/webhooks/provider", headers=GQL, json={}).status_code == 403
