import importlib.util, pathlib
import mongomock
import pytest
from fastapi.testclient import TestClient
import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from shared import internal_jwt

ROOT = pathlib.Path(__file__).resolve().parent.parent
PW = "Clave1234"


class FakeProvider:
    def __init__(self): self.prev = {}
    def get(self, ref): return {"current": f"valor-{ref}", "previous": self.prev.get(ref)}


def load_auth():
    spec = importlib.util.spec_from_file_location("auth_main", ROOT / "auth" / "main.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def ctx():
    mod = load_auth()
    db = mongomock.MongoClient()["auth_db"]
    mod.ensure_indexes(db)
    prov = FakeProvider()
    mod.app.dependency_overrides[mod.get_db] = lambda: db
    mod.app.dependency_overrides[mod.get_provider] = lambda: prov
    with TestClient(mod.app) as c:
        yield c, db, prov, mod


GW = {"X-Caller": "gateway", "X-Caller-Key": "valor-gw-auth"}
CL = {"X-Caller": "clients", "X-Caller-Key": "valor-auth-clients"}


def registrar(c, email="ana@correo.cl", verificar=True):
    r = c.post("/users", json={"email": email, "password": PW}, headers=CL)
    assert r.status_code == 201, r.text
    if verificar:
        assert c.post("/verify-email", json={"token": r.json()["verification_token"]}, headers=GW).status_code == 200
    return r.json()


def login(c, email="ana@correo.cl", pw=PW):
    return c.post("/login", json={"email": email, "password": pw}, headers=GW)


def test_sin_credencial_de_servicio_401(ctx):
    c, *_ = ctx
    assert c.post("/login", json={"email": "a@b.cl", "password": PW}).status_code == 401
    assert c.post("/login", json={"email": "a@b.cl", "password": PW},
                  headers={"X-Caller": "gateway", "X-Caller-Key": "mala"}).status_code == 401


def test_cada_llamador_solo_su_accion_403(ctx):
    c, *_ = ctx
    assert c.post("/users", json={"email": "a@b.cl", "password": PW}, headers=GW).status_code == 403
    assert login(c).status_code == 401  # gateway sí puede llamar a login (usuario inexistente → 401)
    assert c.post("/login", json={"email": "a@b.cl", "password": PW}, headers=CL).status_code == 403


def test_acepta_clave_anterior_durante_rotacion(ctx):
    c, _, prov, _ = ctx
    prov.prev["gw-auth"] = "clave-vieja"
    h = {"X-Caller": "gateway", "X-Caller-Key": "clave-vieja"}
    assert c.post("/login", json={"email": "a@b.cl", "password": PW}, headers=h).status_code == 401  # pasó la autenticación


def test_registro_login_y_sesion(ctx):
    c, *_ = ctx
    registrar(c)
    r = login(c)
    assert r.status_code == 200 and r.json()["role"] == "cliente"
    v = c.post("/session/verify", json={"token": r.json()["token"]}, headers=GW)
    assert v.status_code == 200 and v.json()["user_id"] == r.json()["user_id"]


def test_contrasena_argon2_y_token_solo_como_hash(ctx):
    c, db, *_ = ctx
    registrar(c)
    token = login(c).json()["token"]
    user = db.users.find_one({"email": "ana@correo.cl"})
    assert user["password_hash"].startswith("$argon2id$") and PW not in str(user)
    assert token not in str(list(db.sessions.find())) and token not in str(user)


def test_correo_sin_verificar_403(ctx):
    c, *_ = ctx
    registrar(c, verificar=False)
    assert login(c).status_code == 403


def test_credenciales_invalidas_mismo_mensaje(ctx):
    c, *_ = ctx
    registrar(c)
    a, b = login(c, pw="Otra12345"), login(c, email="nadie@correo.cl")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_bloqueo_tras_intentos_incluye_correo_inexistente(ctx):
    c, *_ = ctx
    registrar(c)
    for email in ("ana@correo.cl", "fantasma@correo.cl"):
        for _ in range(5):
            assert login(c, email=email, pw="Mala12345").status_code == 401
        assert login(c, email=email, pw="Mala12345").status_code == 429
    assert login(c).status_code == 429  # ni con la clave correcta mientras dura el bloqueo


def test_logout_revoca_la_sesion(ctx):
    c, *_ = ctx
    registrar(c)
    t = login(c).json()["token"]
    assert c.post("/logout", json={"token": t}, headers=GW).status_code == 204
    assert c.post("/session/verify", json={"token": t}, headers=GW).status_code == 401


def test_sesion_vencida_401(ctx):
    c, db, *_ = ctx
    registrar(c)
    t = login(c).json()["token"]
    db.sessions.update_many({}, {"$set": {"expires_at": load_auth().now().replace(year=2000)}})
    assert c.post("/session/verify", json={"token": t}, headers=GW).status_code == 401


def test_duplicado_409_y_clave_debil_400(ctx):
    c, *_ = ctx
    registrar(c)
    assert c.post("/users", json={"email": "ANA@correo.cl", "password": PW}, headers=CL).status_code == 409
    assert c.post("/users", json={"email": "b@correo.cl", "password": "sololetras"}, headers=CL).status_code == 400
    assert c.post("/users", json={"email": "no-es-correo", "password": PW}, headers=CL).status_code == 400


def test_no_se_puede_crear_administrador_por_http(ctx):
    c, db, *_ = ctx
    r = c.post("/users", json={"email": "x@correo.cl", "password": PW, "role": "administrador"}, headers=CL)
    assert r.status_code == 201 and db.users.find_one({"email": "x@correo.cl"})["role"] == "cliente"


# ---- añadidos para clients y administración ----
def test_clients_puede_borrar_usuario_y_sus_sesiones(ctx):
    c, db, *_ = ctx
    uid = registrar(c)["id"]
    login(c)
    assert db.sessions.count_documents({}) == 1
    assert c.delete(f"/users/{uid}", headers=GW).status_code == 403          # el gateway no borra cuentas
    assert c.delete(f"/users/{uid}", headers=CL).status_code == 204
    assert db.users.count_documents({}) == 0 and db.sessions.count_documents({}) == 0
    assert c.delete(f"/users/{uid}", headers=CL).status_code == 404 and c.delete("/users/xx", headers=CL).status_code == 404


def test_listado_de_usuarios_solo_administrador_sin_hashes(ctx):
    c, _, _, mod = ctx
    registrar(c)
    ident = lambda role: GW | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", "u", role, "auth", "cid")}
    assert c.get("/users", headers=GW).status_code == 401
    assert c.get("/users", headers=ident("cliente")).status_code == 403
    r = c.get("/users", headers=ident("administrador"))
    assert r.status_code == 200 and r.json()[0]["email"] == "ana@correo.cl"
    assert "password" not in r.text and "hash" not in r.text


def test_seed_del_personal_usa_contrasenas_del_entorno(ctx, monkeypatch):
    c, db, _, mod = ctx
    mod.seed_staff(db)
    assert db.users.count_documents({}) == 0                                  # sin variables no se crea nada
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "AdminDemo123"); monkeypatch.setenv("SEED_CAJERO_PASSWORD", "CajeroDemo123")
    mod.seed_staff(db); mod.seed_staff(db)
    assert sorted(u["role"] for u in db.users.find()) == ["administrador", "cajero"]
    t = c.post("/login", json={"email": "admin@alsahara.cl", "password": "AdminDemo123"}, headers=GW)
    assert t.status_code == 200 and t.json()["role"] == "administrador"
