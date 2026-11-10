import importlib.util, json, pathlib, sys
import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "graphql-gateway"))
from shared import internal_jwt

A, B = "a" * 24, "b" * 24          # pedidos de user-1
OTRO = "c" * 24                     # pedido de user-2
KEYS = {"svc-orders": "valor-gql-orders-de-prueba-32-bytes", "svc-inventory": "valor-gql-inventory-de-prueba-32-bytes", "svc-payments": "valor-gql-payments-de-prueba-32-bytes"}
AUD = {"svc-orders": "orders", "svc-inventory": "inventory", "svc-payments": "payments"}
CATALOGO = {"kebab-mixto": {"id": "p1", "slug": "kebab-mixto", "nombre": "Kebab Mixto", "categoria": "carnes", "descripcion": "Brochetas",
                            "imagen": "assets/img/platos/kebab-mixto.jpg", "precio": 13990, "disponible": True},
            "baklava": {"id": "p2", "slug": "baklava", "nombre": "Baklava", "categoria": "postres", "descripcion": None, "imagen": None,
                        "precio": 4990, "disponible": False}}


def pedido(oid, owner, estado="PAGADO", slugs=("kebab-mixto", "baklava")):
    items = [{"productId": "x", "slug": s, "nombre": CATALOGO[s]["nombre"], "precioUnitario": CATALOGO[s]["precio"], "cantidad": 1,
              "subtotal": CATALOGO[s]["precio"]} for s in slugs]
    return {"id": oid, "estado": estado, "tipo": "DELIVERY", "total": sum(i["subtotal"] for i in items), "comentario": "", "direccionEntrega": "Av. 1",
            "comuna": "Viña del Mar", "motivoAnulacion": None, "creadoEn": "2026-11-03T12:00:00Z", "items": items,
            "historial": [{"estado": "CREADO", "ts": "2026-11-03T12:00:00Z"}, {"estado": estado, "ts": "2026-11-03T12:05:00Z"}],
            "boleta": {"numero": 7, "emitidaEn": "2026-11-03T12:05:00Z"}, "_owner": owner}


class FakeProvider:
    def get(self, ref): return {"current": f"valor-{ref}-de-prueba-32-bytes", "previous": None}


class Upstream:
    def __init__(self):
        self.calls, self.mode = [], {}
        self.orders = {A: pedido(A, "user-1"), B: pedido(B, "user-1", "CREADO"), OTRO: pedido(OTRO, "user-2")}
        self.pagos = {A: {"id": "pay1", "orderId": A, "estado": "APROBADO", "monto": self.orders[A]["total"], "proveedor": "sim"}}

    def who(self, req):
        h = req.headers
        host = req.url.host
        assert h["x-caller"] == "graphql-gateway" and h["x-caller-key"] == KEYS[host], "credencial de tramo incorrecta"
        claims = internal_jwt.verify(h["x-internal-identity"], ["valor-internal-jwt-de-prueba-32-bytes"], AUD[host])
        assert jwt_issuer(h["x-internal-identity"]) == "graphql-gateway"
        return claims["sub"], claims["role"]

    def handler(self, req: httpx.Request) -> httpx.Response:
        host, path, params = req.url.host, req.url.path, dict(req.url.params)
        sub, role = self.who(req)
        self.calls.append((host, req.method, path, params, sub, role))
        mode = self.mode.get(host)
        if mode == "timeout": raise httpx.ReadTimeout("t", request=req)
        if mode == "down": raise httpx.ConnectError("x", request=req)
        if mode == "500": return httpx.Response(500, text="Traceback con secretos")
        if mode == "badjson": return httpx.Response(200, text="<<no es json>>")
        staff = role in ("cajero", "administrador")

        def vis(o): return o if staff or o["_owner"] == sub else None
        def out(o):
            d = {k: v for k, v in o.items() if k != "_owner"}
            if staff: d |= {"cliente": {"id": "cl1", "nombre": "Ana Pérez", "telefono": "+56912345678"}, "requiereReembolso": False}
            return d

        if host == "svc-inventory":
            wanted = params["slugs"].split(",")
            return httpx.Response(200, json=[CATALOGO[s] for s in wanted if s in CATALOGO])
        if host == "svc-payments":
            ids = params["ids"].split(",")
            return httpx.Response(200, json={i: p for i, p in self.pagos.items() if i in ids and (staff or self.orders[i]["_owner"] == sub)})
        if path == "/orders":
            return httpx.Response(200, json=[out(o) for o in self.orders.values() if vis(o)])
        oid = path.split("/")[2]
        o = self.orders.get(oid)
        if not o or not vis(o): return httpx.Response(404, json={"detail": "no"})
        if req.method == "POST":
            if o["estado"] != "CREADO": return httpx.Response(409, json={"detail": "no"})
            if len(json.loads(req.content)["motivo"]) < 5: return httpx.Response(422, json={"detail": "x"})
            o["estado"] = "CANCELADO"; o["motivoAnulacion"] = json.loads(req.content)["motivo"]
        return httpx.Response(200, json=out(o))

    def to(self, host): return [c for c in self.calls if c[0] == host]


def jwt_issuer(token):
    import jwt
    return jwt.decode(token, options={"verify_signature": False})["iss"]


def make(settings=None):
    spec = importlib.util.spec_from_file_location("gql_main", ROOT / "graphql-gateway" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    up = Upstream()
    app = mod.create_app(provider=FakeProvider(), client=httpx.AsyncClient(transport=httpx.MockTransport(up.handler)), settings=settings)
    return TestClient(app), up


@pytest.fixture()
def ctx():
    return make()


def gw(role="cliente", uid="user-1", aud="graphql-gateway", key="valor-gw-graphql-de-prueba-32-bytes"):
    return {"X-Caller": "gateway", "X-Caller-Key": key,
            "X-Internal-Identity": internal_jwt.sign("valor-internal-jwt-de-prueba-32-bytes", uid, role, aud, "cid")}


def gql(c, query, variables=None, headers=None, **kw):
    return c.post("/graphql", json={"query": query, "variables": variables, **kw}, headers=headers or gw())


RESUMEN = "query($id: ID!){ resumenPedido(id: $id){ id estado total items{ nombre cantidad producto{ nombre imagen disponible } } pago{ estado monto } boleta{ numero } } }"


# ------------------------------------------------------------------ agregación
def test_une_pedido_catalogo_y_pago_con_una_llamada_por_servicio(ctx):
    c, up = ctx
    r = gql(c, RESUMEN, {"id": A})
    assert r.status_code == 200 and "errors" not in r.json()
    d = r.json()["data"]["resumenPedido"]
    assert d["estado"] == "PAGADO" and d["boleta"] == {"numero": 7} and d["pago"] == {"estado": "APROBADO", "monto": d["total"]}
    assert [i["producto"]["nombre"] for i in d["items"]] == ["Kebab Mixto", "Baklava"]
    assert d["items"][1]["producto"]["disponible"] is False
    # batching: dos platos → UNA llamada a inventory; un pago → UNA llamada a payments
    assert len(up.to("svc-inventory")) == 1 and set(up.to("svc-inventory")[0][3]["slugs"].split(",")) == {"kebab-mixto", "baklava"}
    assert len(up.to("svc-payments")) == 1 and len(up.to("svc-orders")) == 1


def test_cada_destino_recibe_su_credencial_y_la_identidad_del_usuario(ctx):
    c, up = ctx
    gql(c, RESUMEN, {"id": A})
    assert {(h, sub, role) for h, _, _, _, sub, role in up.calls} == {(h, "user-1", "cliente") for h in KEYS}   # who() ya verificó clave, audiencia y emisor


def test_lista_con_varios_pedidos_no_repite_llamadas(ctx):
    c, up = ctx
    r = gql(c, "{ misPedidos(limit: 10){ id items{ nombre producto{ slug } } pago{ estado } } }")
    assert [p["id"] for p in r.json()["data"]["misPedidos"]] == [A, B]       # el pedido ajeno no aparece
    assert len(up.to("svc-orders")) == 1 and len(up.to("svc-inventory")) == 1 and len(up.to("svc-payments")) == 1
    assert set(up.to("svc-payments")[0][3]["ids"].split(",")) == {A, B}
    pagos = {p["id"]: p["pago"] for p in r.json()["data"]["misPedidos"]}
    assert pagos[A] == {"estado": "APROBADO"} and pagos[B] is None


# ------------------------------------------------------------------ autorización
def test_pedido_ajeno_devuelve_null_sin_revelar_nada(ctx):
    c, up = ctx
    r = gql(c, RESUMEN, {"id": OTRO})
    assert r.json() == {"data": {"resumenPedido": None}}
    assert gql(c, RESUMEN, {"id": "f" * 24}).json() == r.json()                # inexistente se ve igual que ajeno
    assert up.to("svc-inventory") == [] and up.to("svc-payments") == []         # y no se consultó nada más
    assert gql(c, RESUMEN, {"id": OTRO}, headers=gw("cajero", "staff-1")).json()["data"]["resumenPedido"]["id"] == OTRO


def test_campos_de_personal_prohibidos_para_el_cliente(ctx):
    c, _ = ctx
    q = "query($id: ID!){ resumenPedido(id: $id){ id cliente{ nombre telefono } requiereReembolso } }"
    r = gql(c, q, {"id": A}).json()
    assert r["data"]["resumenPedido"] == {"id": A, "cliente": None, "requiereReembolso": None}
    assert {e["extensions"]["code"] for e in r["errors"]} == {"FORBIDDEN"} and len(r["errors"]) == 2
    assert "Ana" not in json.dumps(r) and "56912345678" not in json.dumps(r)
    s = gql(c, q, {"id": A}, headers=gw("cajero", "staff-1")).json()
    assert s["data"]["resumenPedido"]["cliente"] == {"nombre": "Ana Pérez", "telefono": "+56912345678"} and "errors" not in s


def test_no_se_puede_pasar_de_un_cliente_a_otro_con_variables(ctx):
    c, _ = ctx
    q = "query($id: ID!){ resumenPedido(id: $id){ id } }"
    assert gql(c, q, {"id": "../orders"}).json()["errors"][0]["extensions"]["code"] == "BAD_REQUEST"
    assert gql(c, q, {"id": A + "/cancel"}).json()["errors"][0]["extensions"]["code"] == "BAD_REQUEST"


# ------------------------------------------------------------------ errores parciales y fallos
def test_si_inventory_cae_el_resto_de_la_respuesta_sigue(ctx):
    c, up = ctx
    up.mode["svc-inventory"] = "down"
    r = gql(c, RESUMEN, {"id": A}).json()
    d = r["data"]["resumenPedido"]
    assert d["estado"] == "PAGADO" and d["pago"]["estado"] == "APROBADO" and [i["producto"] for i in d["items"]] == [None, None]
    assert {e["extensions"]["code"] for e in r["errors"]} == {"UPSTREAM_UNAVAILABLE"} and "svc-inventory" not in json.dumps(r)


def test_si_payments_tarda_demasiado_solo_falla_el_pago(ctx):
    c, up = ctx
    up.mode["svc-payments"] = "timeout"
    r = gql(c, RESUMEN, {"id": A}).json()
    assert r["data"]["resumenPedido"]["pago"] is None and r["data"]["resumenPedido"]["items"][0]["producto"]["nombre"] == "Kebab Mixto"
    assert r["errors"][0]["extensions"]["code"] == "UPSTREAM_TIMEOUT" and r["errors"][0]["path"] == ["resumenPedido", "pago"]


def test_si_orders_cae_no_hay_datos_y_el_error_es_generico(ctx):
    c, up = ctx
    up.mode["svc-orders"] = "500"
    r = gql(c, RESUMEN, {"id": A}).json()
    assert r["data"]["resumenPedido"] is None and r["errors"][0]["extensions"]["code"] == "UPSTREAM_UNAVAILABLE" and "Traceback" not in json.dumps(r)


def test_excepciones_inesperadas_no_filtran_detalles(ctx):
    c, up = ctx
    up.mode["svc-orders"] = "badjson"
    r = gql(c, RESUMEN, {"id": A}).json()
    assert r["errors"][0]["message"] == "Error interno" and r["errors"][0]["extensions"]["code"] == "INTERNAL" and "json" not in json.dumps(r).lower().replace("internal", "")


# ------------------------------------------------------------------ mutación
def test_anular_delega_en_orders_y_respeta_sus_reglas(ctx):
    c, up = ctx
    m = "mutation($id: ID!, $m: String!){ anularPedido(id: $id, motivo: $m){ estado motivoAnulacion } }"
    ok = gql(c, m, {"id": B, "m": "Me equivoqué de plato"}).json()
    assert ok["data"]["anularPedido"] == {"estado": "CANCELADO", "motivoAnulacion": "Me equivoqué de plato"}
    assert gql(c, m, {"id": B, "m": "Otra vez por favor"}).json()["errors"][0]["extensions"]["code"] == "CONFLICT"      # orders dice 409
    assert gql(c, m, {"id": OTRO, "m": "Es mío ahora"}).json()["errors"][0]["extensions"]["code"] == "NOT_FOUND"        # ajeno
    assert gql(c, m, {"id": A, "m": "no"}).json()["errors"][0]["extensions"]["code"] in ("BAD_REQUEST", "CONFLICT")


# ------------------------------------------------------------------ límites
def test_paginacion_acotada(ctx):
    c, up = ctx
    for lim in (0, 21, -1):
        r = gql(c, "query($l: Int){ misPedidos(limit: $l){ id } }", {"l": lim}).json()
        assert r["errors"][0]["extensions"]["code"] == "BAD_REQUEST"
    assert up.to("svc-orders") == []


def test_limite_de_costo_frena_consultas_masivas(ctx):
    c, up = ctx
    pesada = "{ misPedidos(limit: 20){ id estado items{ nombre cantidad producto{ nombre imagen } } historial{ estado ts } } }"
    r = gql(c, pesada)
    assert r.status_code == 400 and r.json()["errors"][0]["extensions"]["code"] == "COST_LIMIT" and up.calls == []
    assert gql(c, "{ misPedidos(limit: 5){ id estado items{ nombre } } }").status_code == 200
    con_variable = "query($l: Int){ misPedidos(limit: $l){ id estado items{ nombre cantidad producto{ nombre imagen } } historial{ estado ts } } }"
    assert gql(c, con_variable, {"l": 1}).status_code == 400          # con variable se asume el peor caso


def test_limite_de_profundidad_y_campos_raiz():
    c, up = make({"max_depth": 3})
    r = gql(c, "{ misPedidos{ items{ producto{ nombre } } } }")
    assert r.status_code == 400 and r.json()["errors"][0]["extensions"]["code"] == "DEPTH_LIMIT"
    c2, _ = make()
    muchos = "{ " + " ".join(f'a{i}: resumenPedido(id: "{A}"){{ id }}' for i in range(6)) + " }"
    assert gql(c2, muchos).json()["errors"][0]["extensions"]["code"] == "TOO_MANY_FIELDS"


def test_introspeccion_deshabilitada_pero_typename_si(ctx):
    c, _ = ctx
    r = gql(c, "{ __schema { types { name } } }")
    assert r.status_code == 400 and r.json()["errors"][0]["extensions"]["code"] == "INTROSPECTION_DISABLED"
    assert gql(c, "{ __type(name: \"Query\") { name } }").status_code == 400
    assert gql(c, "{ __typename }").json() == {"data": {"__typename": "Query"}}
    c2, _ = make({"introspection": True})
    assert gql(c2, "{ __schema { queryType { name } } }").json()["data"]["__schema"]["queryType"]["name"] == "Query"


def test_consultas_invalidas_se_rechazan_antes_de_ejecutar(ctx):
    c, up = ctx
    assert gql(c, "{ resumenPedido(id: ").json()["errors"][0]["extensions"]["code"] == "SYNTAX_ERROR"
    assert gql(c, f'{{ resumenPedido(id: "{A}") {{ campoInexistente }} }}').json()["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"
    ciclo = f'query {{ resumenPedido(id: "{A}") {{ ...F }} }} fragment F on ResumenPedido {{ id ...G }} fragment G on ResumenPedido {{ ...F }}'
    assert gql(c, ciclo).status_code == 400
    dos = "query A { misPedidos { id } } query B { misPedidos { id } }"
    assert gql(c, dos).status_code == 400 and gql(c, dos, operationName="B").status_code == 200
    assert c.post("/graphql", json={"query": "{ __typename }" + " " * 6000}, headers=gw()).status_code == 422     # consulta demasiado larga
    assert c.post("/graphql", json=[{"query": "{ __typename }"}], headers=gw()).status_code == 422              # sin lotes de operaciones


# ------------------------------------------------------------------ red privada: solo el API Gateway entra
def test_solo_el_api_gateway_con_identidad_valida(ctx):
    c, up = ctx
    q = {"query": "{ __typename }"}
    assert c.post("/graphql", json=q).status_code == 401
    assert c.post("/graphql", json=q, headers={"X-Caller": "gateway", "X-Caller-Key": "mala"}).status_code == 401
    assert c.post("/graphql", json=q, headers={"X-Caller": "gateway", "X-Caller-Key": "valor-gw-graphql-de-prueba-32-bytes"}).status_code == 401         # sin identidad
    assert c.post("/graphql", json=q, headers=gw(aud="orders")).status_code == 401                                                    # token de otro destino
    assert c.post("/graphql", json=q, headers={"X-Caller": "orders", "X-Caller-Key": "valor-gql-orders-de-prueba-32-bytes"}).status_code == 401          # llamador desconocido
    assert c.post("/graphql", json=q, headers=gw(role="intruso")).status_code == 403
    assert c.get("/docs").status_code == 404 and c.get("/graphql").status_code == 405
    assert up.calls == []
