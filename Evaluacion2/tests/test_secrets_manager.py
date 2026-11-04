import importlib, json, pathlib, sys
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
import gen_secrets


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    gen_secrets.generate(out=tmp_path, policy_path=ROOT / "secrets-manager" / "policy.json")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path / "manager"))
    monkeypatch.setenv("POLICY_PATH", str(ROOT / "secrets-manager" / "policy.json"))
    sys.path.insert(0, str(ROOT / "secrets-manager"))
    main = importlib.import_module("main"); importlib.reload(main)
    keys = json.loads((tmp_path / "service_keys.json").read_text())
    with TestClient(main.app) as c:
        yield c, keys


def h(keys, sid): return {"X-Service-Id": sid, "X-Service-Key": keys[sid]}


def test_sin_credencial_401(ctx):
    c, _ = ctx
    assert c.get("/secrets/gw-orders").status_code == 401


def test_clave_incorrecta_401(ctx):
    c, _ = ctx
    assert c.get("/secrets/gw-orders", headers={"X-Service-Id": "orders", "X-Service-Key": "mala"}).status_code == 401


def test_consumidor_autorizado_200(ctx):
    c, k = ctx
    r = c.get("/secrets/orders-payments", headers=h(k, "orders"))
    assert r.status_code == 200 and r.json()["current"] and r.json()["previous"] is None


def test_consumidor_sin_permiso_403(ctx):
    c, k = ctx
    assert c.get("/secrets/orders-payments", headers=h(k, "inventory")).status_code == 403   # no es par
    assert c.get("/secrets/db-orders", headers=h(k, "payments")).status_code == 403          # BD ajena
    assert c.get("/secrets/no-existe", headers=h(k, "orders")).status_code == 403            # no revela existencia


def test_solo_admin_rota_y_queda_clave_anterior(ctx):
    c, k = ctx
    antes = c.get("/secrets/gw-orders", headers=h(k, "orders")).json()["current"]
    assert c.post("/admin/rotate/gw-orders", headers=h(k, "orders")).status_code == 403
    assert c.post("/admin/rotate/gw-orders", headers=h(k, "admin-cli")).status_code == 200
    d = c.get("/secrets/gw-orders", headers=h(k, "orders")).json()
    assert d["current"] != antes and d["previous"] == antes


def test_gen_secrets_separa_lo_que_ve_cada_componente(tmp_path):
    gen_secrets.generate(out=tmp_path, policy_path=ROOT / "secrets-manager" / "policy.json")
    assert sorted(p.name for p in (tmp_path / "manager").iterdir()) == ["service_key_hashes.json", "store.json"]
    store = json.loads((tmp_path / "manager" / "store.json").read_text())
    init = (tmp_path / "mongo-init" / "init.js").read_text()
    for svc in ("auth", "clients", "inventory", "orders", "payments"):
        assert f'getSiblingDB("{svc}_db").createUser({{user: "{svc}"' in init
        assert store[f"db-{svc}"]["current"] in init          # misma clave que entrega el gestor
    assert "service_keys" not in init and (tmp_path / "mongo_root_password").read_text()
    assert "SERVICE_KEY=" in (tmp_path / "env" / "gateway.env").read_text()
    assert f"WEBHOOK_SECRET={store['prov-webhook']['current']}" in (tmp_path / "env" / "provider-sim.env").read_text()
    assert "WEBHOOK_SECRET" not in (tmp_path / "env" / "payments.env").read_text()
    seed = (tmp_path / "seed.env").read_text()
    assert "SEED_ADMIN_PASSWORD=" in seed and "SEED_CAJERO_PASSWORD=" in seed


def test_la_auditoria_no_contiene_valores(ctx, caplog):
    c, k = ctx
    caplog.set_level("INFO")
    valor = c.get("/secrets/gw-orders", headers=h(k, "orders")).json()["current"]
    assert valor not in caplog.text and "gw-orders" in caplog.text
