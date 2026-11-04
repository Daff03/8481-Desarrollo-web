import importlib.util, pathlib, sys
from datetime import datetime, timedelta, timezone
import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import internal_jwt
from shared.events import EventBusUnavailable

GW = {"X-Caller": "gateway", "X-Caller-Key": "valor-gw-orders"}
PAY = {"X-Caller": "payments", "X-Caller-Key": "valor-orders-payments"}
CID = "a" * 24
PRECIOS = {"kebab-mixto": ("Kebab Mixto", 13990), "baklava": ("Baklava", 4990), "falafel-casero": ("Falafel Casero", 8990)}


def as_(role, uid="user-1"):
    return GW | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", uid, role, "orders", "cid")}


class FakeProvider:
    def get(self, ref): return {"current": f"valor-{ref}", "previous": None}


class FakeInventory:
    def __init__(self, mod): self.mod, self.reserved, self.released, self.down, self.release_down = mod, [], [], False, False
    def reserve(self, order_id, items):
        if self.down: raise self.mod.ServiceDown()
        if any(i["productId"] == "agotado" for i in items): raise self.mod.StockError("Sin stock suficiente")
        self.reserved.append((order_id, items))
        lines = [{"productId": "p-" + i["productId"], "slug": i["productId"], "nombre": PRECIOS[i["productId"]][0],
                  "precioUnitario": PRECIOS[i["productId"]][1], "cantidad": i["cantidad"],
                  "subtotal": PRECIOS[i["productId"]][1] * i["cantidad"]} for i in items]
        return {"orderId": order_id, "items": lines, "total": sum(l["subtotal"] for l in lines)}
    def release(self, order_id):
        if self.release_down or self.down: raise self.mod.ServiceDown()
        self.released.append(order_id); return True


class FakeClients:
    def __init__(self, mod):
        self.mod, self.down = mod, False
        self.data = {"nombre": "Ana Pérez Soto", "email": "ana@correo.cl", "telefono": "+56912345678", "id": CID, "run": "12345678-5", "userId": "user-1"}
    def by_user(self, uid):
        if self.down: raise self.mod.ServiceDown()
        return self.data if uid == "user-1" else None
    def by_id(self, cid):
        if self.down: raise self.mod.ServiceDown()
        return self.data if cid == CID else None


class FakeBus:
    def __init__(self): self.sent, self.down = [], False
    def publish(self, t, payload, event_id=None, correlation_id=None):
        if self.down: raise EventBusUnavailable()
        self.sent.append((t, payload, event_id))


@pytest.fixture()
def ctx():
    spec = importlib.util.spec_from_file_location("orders_main", ROOT / "svc-orders" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    db = mongomock.MongoClient()["orders_db"]
    inv, cl, bus = FakeInventory(mod), FakeClients(mod), FakeBus()
    app = mod.app
    app.dependency_overrides.update({mod.get_db: lambda: db, mod.get_provider: lambda: FakeProvider(), mod.get_inventory: lambda: inv,
                                     mod.get_clients: lambda: cl, mod.get_bus: lambda: bus})
    with TestClient(app) as c:
        yield c, db, inv, cl, bus, mod


def body(**kw):
    return {"items": [{"slug": "kebab-mixto", "cantidad": 2}], "direccion": "Av. Libertad 123", "comuna": "Viña del Mar", "comentario": "sin ají"} | kw


def crear(c, uid="user-1", **kw):
    r = c.post("/orders", headers=as_("cliente", uid), json=body(**kw))
    assert r.status_code == 201, r.text
    return r.json()


def pagar(mod, db, order, amount=None, eid=None):
    return mod.apply_payment(db, {"order_id": order["id"], "amount": amount or order["total"], "provider_ref": "sim-1"}, eid or "ev-" + order["id"])


# ------------------------------------------------------------------ cobertura
def test_cobertura_ignora_tildes_y_mayusculas(ctx):
    c, *_ = ctx
    assert c.get("/delivery/coverage?comuna=VINA DEL MAR", headers=GW).json() == {"cubierta": True, "radioKm": 3}
    assert c.get("/delivery/coverage?comuna=Santiago", headers=GW).json()["cubierta"] is False
    assert c.get("/delivery/coverage", headers=GW).status_code == 422
    assert c.get("/delivery/coverage?comuna=Santiago").status_code == 401


# ------------------------------------------------------------------ creación
def test_crea_pedido_con_precio_del_servidor(ctx):
    c, db, inv, *_ = ctx
    r = c.post("/orders", headers=as_("cliente"), json=body(precio=1, total=1, estado="PAGADO", items=[
        {"slug": "kebab-mixto", "cantidad": 1}, {"slug": "kebab-mixto", "cantidad": 1}, {"slug": "baklava", "cantidad": 1}]))
    o = r.json()
    assert r.status_code == 201 and o["estado"] == "CREADO" and o["total"] == 13990 * 2 + 4990
    assert inv.reserved[0][1] == [{"productId": "kebab-mixto", "cantidad": 2}, {"productId": "baklava", "cantidad": 1}]  # repetidos sumados
    assert "cliente" not in o and o["historial"][0]["estado"] == "CREADO"
    assert db.orders.find_one({})["user_id"] == "user-1"


def test_reglas_de_creacion(ctx):
    c, db, inv, cl, *_ = ctx
    h = as_("cliente")
    assert c.post("/orders", headers=h, json=body(comuna="Santiago")).status_code == 422 and inv.reserved == []   # fuera de 3 km
    assert c.post("/orders", headers=h, json={"items": body()["items"]}).status_code == 422                        # delivery sin dirección
    assert c.post("/orders", headers=h, json=body(items=[])).status_code == 422
    assert c.post("/orders", headers=h, json=body(items=[{"slug": "baklava", "cantidad": 21}])).status_code == 422
    assert c.post("/orders", headers=h, json=body(items=[{"slug": "agotado", "cantidad": 1}])).status_code == 422
    assert c.post("/orders", headers=as_("cliente", "otro"), json=body()).status_code == 422                       # sin perfil
    assert c.post("/orders", headers=GW, json=body()).status_code == 401
    assert db.orders.count_documents({}) == 0
    inv.down = True
    assert c.post("/orders", headers=h, json=body()).status_code == 503
    inv.down, cl.down = False, True
    assert c.post("/orders", headers=h, json=body()).status_code == 503


def test_venta_en_local_la_hace_el_personal_con_cliente(ctx):
    c, db, *_ = ctx
    local = {"items": [{"slug": "baklava", "cantidad": 1}], "tipo": "LOCAL"}
    assert c.post("/orders", headers=as_("cajero", "staff"), json=local).status_code == 422            # falta clienteId
    r = c.post("/orders", headers=as_("cajero", "staff"), json=local | {"clienteId": CID})
    assert r.status_code == 201 and r.json()["tipo"] == "LOCAL" and r.json()["direccionEntrega"] is None
    assert db.orders.find_one({})["canal"] == "CAJA" and db.orders.find_one({})["user_id"] == "user-1"


# ------------------------------------------------------------------ propiedad y listados
def test_un_cliente_no_ve_pedidos_ajenos(ctx):
    c, db, *_ = ctx
    o = crear(c)
    assert c.get(f"/orders/{o['id']}", headers=as_("cliente")).status_code == 200
    assert c.get(f"/orders/{o['id']}", headers=as_("cliente", "intruso")).status_code == 404     # no revela que existe
    assert c.get("/orders/no-es-id", headers=as_("cliente")).status_code == 404
    assert c.get("/orders", headers=as_("cliente", "intruso")).json() == []
    assert len(c.get("/orders", headers=as_("cliente")).json()) == 1
    staff = c.get(f"/orders/{o['id']}", headers=as_("cajero", "staff")).json()
    assert staff["cliente"]["nombre"] == "Ana Pérez Soto" and "run" not in str(staff)
    assert c.get("/orders?estado=INVENTADO", headers=as_("cajero", "staff")).status_code == 400


# ------------------------------------------------------------------ pago (único camino a PAGADO)
def test_pago_aprobado_marca_pagado_emite_boleta_y_envia_correo(ctx):
    c, db, _, _, bus, mod = ctx
    o = crear(c)
    assert pagar(mod, db, o) == "paid"
    n = c.get(f"/orders/{o['id']}", headers=as_("cliente")).json()
    assert n["estado"] == "PAGADO" and n["boleta"]["numero"] == 1 and n["despacho"]["estado"] == "PENDIENTE"
    assert [h["estado"] for h in n["historial"]] == ["CREADO", "PAGADO"]
    assert mod.flush_outbox(db, bus) == 1
    t, payload, _ = bus.sent[0]
    assert t == "correo.enviar" and payload["template"] == "boleta" and payload["to"] == "ana@correo.cl" and payload["data"]["total"] == o["total"]
    assert db.orders.find_one({})["boleta"]["enviada_por_correo"] is True


def test_pago_duplicado_o_repetido_no_duplica_nada(ctx):
    c, db, _, _, bus, mod = ctx
    o = crear(c)
    assert pagar(mod, db, o, eid="e1") == "paid"
    assert pagar(mod, db, o, eid="e1") == "duplicate"        # mismo event_id
    assert pagar(mod, db, o, eid="e2") == "noop"             # otro evento del mismo pedido
    assert db.counters.find_one({"_id": "boleta"})["seq"] == 1 and db.outbox.count_documents({}) == 1


def test_pago_alterado_se_rechaza(ctx):
    c, db, _, _, _, mod = ctx
    o = crear(c)
    with pytest.raises(ValueError):
        pagar(mod, db, o, amount=o["total"] - 1000, eid="mal")
    with pytest.raises(ValueError):
        mod.apply_payment(db, {"order_id": "0" * 24, "amount": 1, "provider_ref": "x"}, "fantasma")
    with pytest.raises(ValueError):
        mod.apply_payment(db, {"order_id": "no-id", "amount": 1, "provider_ref": "x"}, "invalido")
    assert db.orders.find_one({})["estado"] == "CREADO" and db.processed_events.count_documents({}) == 0   # el broker puede reintentar


def test_pago_tardio_tras_anular_queda_para_reembolso(ctx):
    c, db, _, _, _, mod = ctx
    o = crear(c)
    c.post(f"/orders/{o['id']}/cancel", headers=as_("cliente"), json={"motivo": "Me arrepentí"})
    assert pagar(mod, db, o) == "late"
    d = db.orders.find_one({})
    assert d["estado"] == "CANCELADO" and d["requiere_reembolso"] and d.get("boleta") is None


def test_no_hay_ruta_http_para_marcar_pagado(ctx):
    c, db, *_ = ctx
    o = crear(c)
    r = c.patch(f"/orders/{o['id']}/status", headers=as_("administrador", "adm"), json={"estado": "PAGADO"})
    assert r.status_code == 422 and db.orders.find_one({})["estado"] == "CREADO"


# ------------------------------------------------------------------ cocina y despacho
def test_ciclo_completo_delivery(ctx):
    c, db, _, _, _, mod = ctx
    staff = as_("cajero", "staff")
    o = crear(c); pagar(mod, db, o)
    assert c.patch(f"/orders/{o['id']}/status", headers=as_("cliente"), json={"estado": "LISTO"}).status_code == 403
    assert c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": "LISTO"}).status_code == 409        # salta un paso
    assert c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": "EN_PREPARACION"}).json()["estado"] == "EN_PREPARACION"
    assert c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": "LISTO"}).json()["estado"] == "LISTO"
    assert c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": "ENTREGADO"}).status_code == 409   # delivery se entrega desde /dispatch
    assert [x["id"] for x in c.get("/dispatch", headers=staff).json()] == [o["id"]]
    assert c.patch(f"/dispatch/{o['id']}", headers=staff, json={"estado": "EN_CAMINO"}).status_code == 422        # falta conductor
    r = c.patch(f"/dispatch/{o['id']}", headers=staff, json={"estado": "EN_CAMINO", "conductor": "Juan Soto"})
    assert r.json()["estado"] == "EN_CAMINO" and r.json()["despacho"]["conductor"] == "Juan Soto" and r.json()["despacho"]["salidaEn"]
    r = c.patch(f"/dispatch/{o['id']}", headers=staff, json={"estado": "ENTREGADO"})
    assert r.json()["estado"] == "ENTREGADO" and r.json()["despacho"]["entregadoEn"]
    assert [h["estado"] for h in r.json()["historial"]] == ["CREADO", "PAGADO", "EN_PREPARACION", "LISTO", "EN_CAMINO", "ENTREGADO"]
    assert c.patch(f"/dispatch/{o['id']}", headers=staff, json={"estado": "ENTREGADO"}).status_code == 409
    assert c.get("/dispatch", headers=as_("cliente")).status_code == 403


def test_pedido_en_local_se_entrega_sin_despacho(ctx):
    c, db, _, _, _, mod = ctx
    staff = as_("cajero", "staff")
    o = c.post("/orders", headers=staff, json={"items": [{"slug": "baklava", "cantidad": 1}], "tipo": "LOCAL", "clienteId": CID}).json()
    pagar(mod, db, o)
    assert "despacho" not in c.get(f"/orders/{o['id']}", headers=staff).json()
    for estado in ("EN_PREPARACION", "LISTO", "ENTREGADO"):
        assert c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": estado}).json()["estado"] == estado
    assert c.patch(f"/dispatch/{o['id']}", headers=staff, json={"estado": "EN_CAMINO", "conductor": "Juan Soto"}).status_code == 404


# ------------------------------------------------------------------ anulación (RF3)
def test_anulacion_con_motivo_conserva_historial_y_devuelve_stock(ctx):
    c, db, inv, *_ = ctx
    o = crear(c)
    h = as_("cliente")
    assert c.post(f"/orders/{o['id']}/cancel", headers=h, json={"motivo": "no"}).status_code == 422             # motivo muy corto
    assert c.post(f"/orders/{o['id']}/cancel", headers=as_("cliente", "intruso"), json={"motivo": "Es mío ahora"}).status_code == 404
    r = c.post(f"/orders/{o['id']}/cancel", headers=h, json={"motivo": "Me equivoqué de plato"})
    assert r.status_code == 200 and r.json()["estado"] == "CANCELADO" and r.json()["motivoAnulacion"] == "Me equivoqué de plato"
    assert [x["estado"] for x in r.json()["historial"]] == ["CREADO", "CANCELADO"] and db.orders.count_documents({}) == 1
    assert inv.released == [o["id"]] and db.orders.find_one({})["stock_liberado"] is True
    assert c.post(f"/orders/{o['id']}/cancel", headers=h, json={"motivo": "Otra vez por favor"}).status_code == 409


def test_quien_puede_anular_segun_el_estado(ctx):
    c, db, _, _, _, mod = ctx
    o = crear(c); pagar(mod, db, o)
    staff = as_("cajero", "staff")
    c.patch(f"/orders/{o['id']}/status", headers=staff, json={"estado": "EN_PREPARACION"})
    assert c.post(f"/orders/{o['id']}/cancel", headers=as_("cliente"), json={"motivo": "Ya no lo quiero"}).status_code == 409   # ya en cocina
    r = c.post(f"/orders/{o['id']}/cancel", headers=staff, json={"motivo": "Se acabó el cordero"})
    assert r.status_code == 200 and r.json()["requiereReembolso"] is True and r.json()["despacho"]["estado"] == "CANCELADO"
    o2 = crear(c); pagar(mod, db, o2)
    assert c.post(f"/orders/{o2['id']}/cancel", headers=as_("cliente"), json={"motivo": "Cambio de planes"}).json()["estado"] == "CANCELADO"  # pagado, aún sin cocina


def test_si_inventory_no_responde_la_devolucion_se_reintenta(ctx):
    c, db, inv, *_ = ctx
    o = crear(c)
    inv.release_down = True
    assert c.post(f"/orders/{o['id']}/cancel", headers=as_("cliente"), json={"motivo": "Cambio de planes"}).status_code == 200
    assert db.orders.find_one({})["stock_liberado"] is False
    inv.release_down = False
    ctx[5].retry_releases(db, inv)
    assert db.orders.find_one({})["stock_liberado"] is True and inv.released == [o["id"]]


def test_pedido_sin_pagar_vence_y_devuelve_stock(ctx):
    c, db, inv, _, _, mod = ctx
    viejo, nuevo, pagado = crear(c), crear(c), crear(c)
    pagar(mod, db, pagado)
    db.orders.update_many({"_id": {"$in": [ObjectId(viejo["id"]), ObjectId(pagado["id"])]}},
                          {"$set": {"creado_en": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)}})
    assert mod.expire_unpaid(db, inv) == 1
    estados = {str(o["_id"]): o["estado"] for o in db.orders.find()}
    assert estados[viejo["id"]] == "CANCELADO" and estados[nuevo["id"]] == "CREADO" and estados[pagado["id"]] == "PAGADO"
    assert inv.released == [viejo["id"]]
    assert db.orders.find_one({"estado": "CANCELADO"})["motivo_anulacion"] == "Pago no recibido a tiempo"


# ------------------------------------------------------------------ boleta
def test_boleta_solo_tras_el_pago_y_solo_del_dueno(ctx):
    c, db, _, _, _, mod = ctx
    o = crear(c)
    assert c.get(f"/orders/{o['id']}/receipt", headers=as_("cliente")).status_code == 404
    pagar(mod, db, o)
    r = c.get(f"/orders/{o['id']}/receipt", headers=as_("cliente")).json()
    assert r["numero"] == 1 and r["total"] == o["total"] and r["items"][0]["nombre"] == "Kebab Mixto"
    assert c.get(f"/orders/{o['id']}/receipt", headers=as_("cliente", "intruso")).status_code == 404


def test_boletas_correlativas_y_recuperacion_tras_caida(ctx):
    c, db, inv, _, bus, mod = ctx
    a, b = crear(c), crear(c)
    pagar(mod, db, a); pagar(mod, db, b)
    assert sorted(o["boleta"]["numero"] for o in db.orders.find()) == [1, 2]
    db.orders.update_one({"_id": db.orders.find_one({"boleta.numero": 2})["_id"]}, {"$set": {"boleta": None}})  # cayó antes de emitirla
    mod.maintenance(db, inv, bus)
    assert db.orders.find_one({"boleta.numero": 3}) is not None


# ------------------------------------------------------------------ uso interno de payments
def test_payments_consulta_el_monto_real(ctx):
    c, *_ = ctx
    o = crear(c)
    r = c.get(f"/internal/orders/{o['id']}", headers=PAY)
    assert r.status_code == 200 and r.json() == {"id": o["id"], "estado": "CREADO", "total": o["total"], "userId": "user-1", "clienteId": CID}
    assert c.get(f"/internal/orders/{o['id']}", headers=GW).status_code == 403
    assert c.get(f"/internal/orders/{o['id']}", headers=PAY | {"X-Caller-Key": "mala"}).status_code == 401
    assert c.get("/internal/orders/" + "0" * 24, headers=PAY).status_code == 404


# ------------------------------------------------------------------ reservas de mesa
def futuro(dias=3):
    return (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%dT20:00")


def reserva(**kw):
    return {"nombre": "Luis Rojas Díaz", "email": "Luis@Correo.cl", "personas": 4, "fechaHora": futuro(), "mensaje": "cumpleaños"} | kw


def test_reserva_anonima_valida_y_notifica(ctx):
    c, db, _, _, bus, mod = ctx
    r = c.post("/reservations", headers=GW, json=reserva())
    assert r.status_code == 201 and r.json()["estado"] == "PENDIENTE"
    assert db.reservations_mesa.find_one({})["email"] == "luis@correo.cl" and db.reservations_mesa.find_one({})["user_id"] is None
    mod.flush_outbox(db, bus)
    assert bus.sent[0][1]["template"] == "reserva" and bus.sent[0][1]["data"]["estado"] == "PENDIENTE"
    r2 = c.post("/reservations", headers=as_("cliente"), json=reserva())
    assert db.reservations_mesa.find_one({"_id": ObjectId(r2.json()["id"])})["user_id"] == "user-1"


def test_reserva_rechaza_datos_invalidos(ctx):
    c, db, *_ = ctx
    for malo in ({"fechaHora": "2020-01-01T20:00"}, {"fechaHora": futuro(120)}, {"fechaHora": "mañana"}, {"personas": 0}, {"personas": 50},
                 {"email": "x"}, {"nombre": "Luis"}):
        assert c.post("/reservations", headers=GW, json=reserva(**malo)).status_code == 422, malo
    assert db.reservations_mesa.count_documents({}) == 0


def test_personal_gestiona_reservas(ctx):
    c, db, _, _, bus, mod = ctx
    rid = c.post("/reservations", headers=GW, json=reserva()).json()["id"]
    assert c.get("/reservations", headers=as_("cliente")).status_code == 403
    assert c.get("/reservations", headers=GW).status_code == 401
    assert c.get("/reservations?estado=PENDIENTE", headers=as_("cajero", "s")).json()[0]["id"] == rid
    assert c.patch(f"/reservations/{rid}", headers=as_("cliente"), json={"estado": "CONFIRMADA"}).status_code == 403
    assert c.patch(f"/reservations/{rid}", headers=as_("cajero", "s"), json={"estado": "CONFIRMADA"}).json()["estado"] == "CONFIRMADA"
    assert c.patch(f"/reservations/{rid}", headers=as_("cajero", "s"), json={"estado": "RECHAZADA"}).status_code == 409
    assert c.patch(f"/reservations/{rid}", headers=as_("cajero", "s"), json={"estado": "CANCELADA"}).json()["estado"] == "CANCELADA"
    assert c.patch("/reservations/" + "0" * 24, headers=as_("cajero", "s"), json={"estado": "CONFIRMADA"}).status_code == 404
    mod.flush_outbox(db, bus)
    assert [m[1]["data"]["estado"] for m in bus.sent] == ["PENDIENTE", "CONFIRMADA", "CANCELADA"]


# ------------------------------------------------------------------ reporte (RF9)
def test_reporte_cuenta_solo_ventas_pagadas_y_es_de_administrador(ctx):
    c, db, _, _, _, mod = ctx
    a, b, anulado = crear(c), crear(c, items=[{"slug": "baklava", "cantidad": 3}]), crear(c)
    crear(c)  # un pedido sin pagar: no debe contar como venta
    for o in (a, b, anulado):
        pagar(mod, db, o)
    c.post(f"/orders/{anulado['id']}/cancel", headers=as_("cajero", "s"), json={"motivo": "Error de cocina"})
    adm = as_("administrador", "adm")
    assert c.get("/reports/sales", headers=as_("cajero", "s")).status_code == 403
    assert c.get("/reports/sales", headers=GW).status_code == 401
    r = c.get("/reports/sales", headers=adm).json()
    assert r["pedidos"] == 2 and r["total"] == a["total"] + b["total"] and r["ticketPromedio"] == (a["total"] + b["total"]) // 2
    assert r["porTipo"] == [{"tipo": "DELIVERY", "pedidos": 2, "total": a["total"] + b["total"]}]
    assert [(p["slug"], p["unidades"]) for p in r["topPlatos"]] == [("baklava", 3), ("kebab-mixto", 2)] and len(r["porDia"]) == 1
    assert c.get("/reports/sales?desde=2020-01-01&hasta=2020-01-31", headers=adm).json()["pedidos"] == 0
    assert c.get("/reports/sales?desde=2026-02-01&hasta=2026-01-01", headers=adm).status_code == 400
    assert c.get("/reports/sales?desde=2020-01-01&hasta=2026-01-01", headers=adm).status_code == 400


GQL = {"X-Caller": "graphql-gateway", "X-Caller-Key": "valor-gql-orders"}


def as_gql(role, uid="user-1"):
    return GQL | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", uid, role, "orders", "cid", issuer="graphql-gateway")}


def test_graphql_gateway_lee_pedidos_con_la_propiedad_comprobada_por_orders(ctx):
    c, db, *_ = ctx
    o = crear(c)
    assert c.get(f"/orders/{o['id']}", headers=as_gql("cliente")).status_code == 200
    assert c.get(f"/orders/{o['id']}", headers=as_gql("cliente", "intruso")).status_code == 404    # orders sigue decidiendo
    assert len(c.get("/orders", headers=as_gql("cliente")).json()) == 1 and c.get("/orders", headers=as_gql("cliente", "intruso")).json() == []
    assert c.get(f"/orders/{o['id']}", headers=GQL).status_code == 401                              # sin identidad
    assert c.post(f"/orders/{o['id']}/cancel", headers=as_gql("cliente"), json={"motivo": "Cambio de planes"}).status_code == 200


def test_graphql_gateway_no_crea_pedidos_ni_toca_rutas_internas(ctx):
    c, *_ = ctx
    assert c.post("/orders", headers=as_gql("cliente"), json=body()).status_code == 403
    assert c.get("/reports/sales", headers=as_gql("administrador", "adm")).status_code == 403
    assert c.get("/internal/orders/" + "0" * 24, headers=as_gql("administrador", "adm")).status_code == 403
