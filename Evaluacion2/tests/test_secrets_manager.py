import importlib, json, pathlib, sys
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
import gen_secrets


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    gen_secrets.generate(out=tmp_path, policy_path=ROOT / "secrets-manager" / "policy.json")
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
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


def test_la_auditoria_no_contiene_valores(ctx, caplog):
    c, k = ctx
    caplog.set_level("INFO")
    valor = c.get("/secrets/gw-orders", headers=h(k, "orders")).json()["current"]
    assert valor not in caplog.text and "gw-orders" in caplog.text
