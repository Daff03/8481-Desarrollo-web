import importlib.util, pathlib, sys
import mongomock
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import internal_jwt
from shared.events import EventBusUnavailable

GW = {"X-Caller": "gateway", "X-Caller-Key": "valor-gw-clients"}
ORD = {"X-Caller": "orders", "X-Caller-Key": "valor-orders-clients"}
RUN_OK = "12.345.678-5"


def as_(role, uid="u1"):
    return GW | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", uid, role, "clients", "cid")}


class FakeProvider:
    def get(self, ref): return {"current": f"valor-{ref}", "previous": None}


class FakeBus:
    def __init__(self): self.sent, self.down = [], False
    def publish(self, t, payload, event_id=None, correlation_id=None):
        if self.down: raise EventBusUnavailable()
        self.sent.append((t, payload, event_id))


class FakeAuth:
    def __init__(self, mod): self.mod, self.users, self.deleted, self.fail, self.on_create = mod, {}, [], None, None
    def create_user(self, email, password):
        if self.fail: raise self.fail()
        if email in self.users: raise self.mod.AuthConflict()
        uid = f"user-{len(self.users) + 1}"; self.users[email] = uid
        if self.on_create: self.on_create()
        return uid, "token-de-verificacion-" + uid
    def delete_user(self, uid):
        self.deleted.append(uid)
        self.users = {e: u for e, u in self.users.items() if u != uid}


@pytest.fixture()
def ctx():
    spec = importlib.util.spec_from_file_location("clients_main", ROOT / "svc-clients" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    db = mongomock.MongoClient()["clients_db"]
    mod.ensure_indexes(db)
    auth, bus = FakeAuth(mod), FakeBus()
    app = mod.app
    app.dependency_overrides.update({mod.get_db: lambda: db, mod.get_provider: lambda: FakeProvider(),
                                     mod.get_auth: lambda: auth, mod.get_bus: lambda: bus})
    with TestClient(app) as c:
        yield c, db, auth, bus, mod


def datos(**kw):
    base = {"run": RUN_OK, "nombre": "Ana Pérez Soto", "direccion": "Av. Siempre Viva 742", "comuna": "Viña del Mar",
            "provincia": "Valparaíso", "region": "Valparaíso", "fechaNacimiento": "1990-05-20", "sexo": "F",
            "telefono": "+56 9 1234 5678", "email": "Ana@Correo.cl", "password": "Clave1234"}
    return base | kw


def registrar(c, **kw):
    r = c.post("/clients/register", headers=GW, json=datos(**kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_validacion_de_run():
    spec = importlib.util.spec_from_file_location("clients_main2", ROOT / "svc-clients" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.valid_run("12345678-5") and mod.valid_run("11111111-1")
    assert not mod.valid_run("12345678-9") and not mod.valid_run("abc") and not mod.valid_run("1234567-K")


def test_registro_crea_cuenta_perfil_direccion_y_pide_correo(ctx):
    c, db, auth, bus, _ = ctx
    registrar(c)
    assert auth.users == {"ana@correo.cl": "user-1"}
    cl = db.clients.find_one({})
    assert cl["run"] == "12345678-5" and cl["user_id"] == "user-1" and cl["telefono"] == "+56912345678" and "password" not in str(cl)
    adr = list(db.addresses.find({}))
    assert len(adr) == 1 and adr[0]["principal"] and adr[0]["comuna"] == "Viña del Mar"
    t, payload, _ = bus.sent[0]
    assert t == "correo.enviar" and payload["to"] == "ana@correo.cl" and payload["data"]["token"].startswith("token-de-verificacion")
    assert db.outbox.count_documents({}) == 0  # publicado → el token ya no queda guardado


def test_registro_sin_broker_conserva_el_aviso_y_lo_reintenta(ctx):
    c, db, _, bus, mod = ctx
    bus.down = True
    registrar(c)
    assert db.outbox.count_documents({}) == 1 and bus.sent == []
    bus.down = False
    assert mod.flush_outbox(db, bus) == 1 and db.outbox.count_documents({}) == 0 and len(bus.sent) == 1
    assert mod.flush_outbox(db, bus) == 0  # no se envía dos veces


def test_registro_rechaza_datos_invalidos(ctx):
    c, db, auth, *_ = ctx
    for malo in ({"run": "12345678-9"}, {"fechaNacimiento": "2015-01-01"}, {"email": "no-es-correo"}, {"password": "sololetras"},
                 {"nombre": "Ana"}, {"sexo": "X"}, {"telefono": "123"}, {"fechaNacimiento": "1800-01-01"}):
        assert c.post("/clients/register", headers=GW, json=datos(**malo)).status_code == 422, malo
    assert db.clients.count_documents({}) == 0 and auth.users == {}


def test_registro_duplicado_409_sin_crear_cuenta_huerfana(ctx):
    c, db, auth, *_ = ctx
    registrar(c)
    assert c.post("/clients/register", headers=GW, json=datos(email="otra@correo.cl")).status_code == 409   # mismo RUN
    assert "otra@correo.cl" not in auth.users
    assert c.post("/clients/register", headers=GW, json=datos(run="11.111.111-1")).status_code == 409        # mismo correo
    assert db.clients.count_documents({}) == 1


def test_carrera_de_run_deshace_la_cuenta(ctx):
    c, db, auth, *_ = ctx
    auth.on_create = lambda: db.clients.insert_one({"run": "12345678-5", "nombre": "Otro Cliente", "activo": True})
    assert c.post("/clients/register", headers=GW, json=datos()).status_code == 409
    assert auth.deleted == ["user-1"]


def test_auth_caido_503(ctx):
    c, db, auth, _, mod = ctx
    auth.fail = mod.AuthDown
    assert c.post("/clients/register", headers=GW, json=datos()).status_code == 503 and db.clients.count_documents({}) == 0


def test_perfil_propio_y_permisos(ctx):
    c, db, *_ = ctx
    registrar(c)
    assert c.get("/clients/me", headers=GW).status_code == 401
    assert c.get("/clients/me", headers=as_("cajero")).status_code == 403
    me = c.get("/clients/me", headers=as_("cliente", "user-1")).json()
    assert me["nombre"] == "Ana Pérez Soto" and me["run"] == "12345678-5"
    r = c.put("/clients/me", headers=as_("cliente", "user-1"), json={"nombre": "Ana María Pérez", "sexo": "F", "telefono": "912345678", "run": "1-9"})
    assert r.json()["nombre"] == "Ana María Pérez" and r.json()["run"] == "12345678-5"  # el RUN no se cambia
    assert c.get("/clients/me", headers=as_("cliente", "user-desconocido")).status_code == 404


def test_direcciones_maximo_5_y_principal(ctx):
    c, db, *_ = ctx
    registrar(c)
    h = as_("cliente", "user-1")
    nueva = {"alias": "Trabajo", "direccion": "Calle Falsa 123", "comuna": "Concón", "provincia": "Valparaíso", "region": "Valparaíso"}
    ids = [c.post("/clients/me/addresses", headers=h, json=nueva | {"alias": f"d{i}"}).json()["id"] for i in range(4)]
    assert c.post("/clients/me/addresses", headers=h, json=nueva).status_code == 422          # la 6ª
    lista = c.get("/clients/me/addresses", headers=h).json()
    assert len(lista) == 5 and sum(a["principal"] for a in lista) == 1
    assert c.put(f"/clients/me/addresses/{ids[2]}", headers=h, json=nueva | {"principal": True}).json()["principal"] is True
    assert sum(a["principal"] for a in c.get("/clients/me/addresses", headers=h).json()) == 1
    assert c.delete(f"/clients/me/addresses/{ids[2]}", headers=h).status_code == 204          # borrar la principal
    assert sum(a["principal"] for a in c.get("/clients/me/addresses", headers=h).json()) == 1  # otra pasa a principal


def test_no_se_toca_la_direccion_de_otro_cliente(ctx):
    c, db, auth, *_ = ctx
    registrar(c)
    registrar(c, run="11.111.111-1", email="b@correo.cl")
    ajena = str(db.addresses.find_one({"client_id": str(db.clients.find_one({"user_id": "user-2"})["_id"])})["_id"])
    h = as_("cliente", "user-1")
    body = {"alias": "x", "direccion": "Calle Falsa 123", "comuna": "Concón", "provincia": "Valparaíso", "region": "Valparaíso"}
    assert c.put(f"/clients/me/addresses/{ajena}", headers=h, json=body).status_code == 404
    assert c.delete(f"/clients/me/addresses/{ajena}", headers=h).status_code == 404
    assert c.delete("/clients/me/addresses/no-es-id", headers=h).status_code == 404
    assert db.addresses.count_documents({}) == 2


def test_listado_de_personal_enmascara_el_run(ctx):
    c, *_ = ctx
    cid = registrar(c)
    assert c.get("/clients", headers=as_("cliente")).status_code == 403
    lista = c.get("/clients", headers=as_("cajero")).json()
    assert lista[0]["run"] == "12345***-5"
    assert "12345678-5" not in str(lista) and "telefono" not in lista[0]
    assert c.get("/clients?q=pérez", headers=as_("cajero")).json()[0]["id"] == cid
    assert c.get("/clients?q=12.345.678-5", headers=as_("cajero")).json()[0]["id"] == cid
    assert c.get("/clients?q=.*", headers=as_("cajero")).json() == []   # la búsqueda no interpreta regex
    assert c.get(f"/clients/{cid}", headers=as_("cajero")).json()["run"] == "12345678-5"


def test_admin_registra_en_local_sin_cuenta(ctx):
    c, db, auth, *_ = ctx
    body = datos(run="11.111.111-1")
    for k in ("email", "password", "direccion", "comuna", "provincia", "region"): body.pop(k)
    assert c.post("/clients", headers=as_("cajero"), json=body).status_code == 403
    r = c.post("/clients", headers=as_("administrador"), json=body)
    assert r.status_code == 201 and auth.users == {} and "user_id" not in db.clients.find_one({"run": "11111111-1"})
    assert c.post("/clients", headers=as_("administrador"), json=body).status_code == 409


def test_baja_anonimiza_y_borra_la_cuenta(ctx):
    c, db, auth, *_ = ctx
    cid = registrar(c)
    assert c.delete(f"/clients/{cid}", headers=as_("cajero")).status_code == 403
    assert c.delete(f"/clients/{cid}", headers=as_("administrador")).status_code == 204
    cl = db.clients.find_one({})
    assert auth.deleted == ["user-1"] and cl["activo"] is False and cl["nombre"] == "(baja)" and cl["telefono"] is None
    assert "user_id" not in cl and db.addresses.count_documents({}) == 0
    assert c.get("/clients", headers=as_("cajero")).json() == [] and c.delete(f"/clients/{cid}", headers=as_("administrador")).status_code == 404
    registrar(c)  # el RUN puede volver a registrarse


def test_rutas_internas_solo_para_orders(ctx):
    c, *_ = ctx
    cid = registrar(c)
    r = c.get("/internal/clients/by-user/user-1", headers=ORD)
    assert r.status_code == 200 and r.json()["id"] == cid and len(r.json()["direcciones"]) == 1
    assert c.get(f"/internal/clients/{cid}", headers=ORD).status_code == 200
    assert c.get("/internal/clients/by-user/user-1", headers=GW).status_code == 403
    assert c.get("/internal/clients/by-user/user-1").status_code == 401
    assert c.get("/internal/clients/by-user/nadie", headers=ORD).status_code == 404
    assert c.get("/clients/me", headers=ORD).status_code == 403   # orders no usa rutas públicas


def test_vista_interna_incluye_el_usuario_para_orders(ctx):
    c, *_ = ctx
    registrar(c)
    assert c.get("/internal/clients/by-user/user-1", headers=ORD).json()["userId"] == "user-1"
