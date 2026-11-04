import importlib.util, pathlib, sys
import mongomock
import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import internal_jwt


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


class FakeProvider:
    def __init__(self): self.prev = {}
    def get(self, ref): return {"current": f"valor-{ref}", "previous": self.prev.get(ref)}


GW = {"X-Caller": "gateway", "X-Caller-Key": "valor-gw-inventory"}
ORD = {"X-Caller": "orders", "X-Caller-Key": "valor-orders-inventory"}


def as_(role, aud="inventory", uid="u1"):
    return GW | {"X-Internal-Identity": internal_jwt.sign("valor-internal-jwt", uid, role, aud, "cid")}


@pytest.fixture()
def ctx():
    inv = load("inventory_main", ROOT / "svc-inventory" / "main.py")
    seed = load("inventory_seed", ROOT / "svc-inventory" / "seed.py")
    db = mongomock.MongoClient()["inventory_db"]
    inv.ensure_indexes(db); seed.seed(db)
    prov = FakeProvider()
    inv.app.dependency_overrides[inv.get_db] = lambda: db
    inv.app.dependency_overrides[inv.get_provider] = lambda: prov
    with TestClient(inv.app) as c:
        yield c, db, prov, seed


def pid(db, slug): return str(db.products.find_one({"slug": slug})["_id"])


def test_seed_12_platos_e_idempotente(ctx):
    c, db, _, seed = ctx
    assert db.products.count_documents({}) == 12 and seed.seed(db) == 12


def test_catalogo_publico_solo_campos_permitidos(ctx):
    c, *_ = ctx
    r = c.get("/products", headers=GW)
    assert r.status_code == 200 and len(r.json()) == 12
    assert set(r.json()[0]) == {"id", "slug", "nombre", "categoria", "precio", "disponible", "descripcion", "imagen", "popular"}


def test_sin_credencial_o_llamador_equivocado(ctx):
    c, *_ = ctx
    assert c.get("/products").status_code == 401
    assert c.get("/products", headers={"X-Caller": "gateway", "X-Caller-Key": "mala"}).status_code == 401
    assert c.get("/products", headers=ORD).status_code == 403          # orders no usa el catálogo público
    assert c.post("/internal/reserve", headers=GW, json={"orderId": "o1", "items": []}).status_code == 403  # el gateway no llega a rutas internas


def test_acepta_clave_anterior_en_rotacion(ctx):
    c, _, prov, _ = ctx
    prov.prev["gw-inventory"] = "vieja"
    assert c.get("/products", headers={"X-Caller": "gateway", "X-Caller-Key": "vieja"}).status_code == 200


def test_filtros_y_validacion(ctx):
    c, db, *_ = ctx
    assert len(c.get("/products?categoria=postres", headers=GW).json()) == 3
    assert c.get("/products?categoria=zzz", headers=GW).status_code == 400
    assert c.get("/products?available=quizas", headers=GW).status_code == 400
    assert c.get("/products?limit=1000", headers=GW).status_code == 422
    db.products.update_one({"slug": "baklava"}, {"$set": {"stock": 0}})
    disp = c.get("/products?available=true", headers=GW).json()
    assert len(disp) == 11 and "baklava" not in [p["slug"] for p in disp]


def test_detalle_por_id_o_slug_y_404(ctx):
    c, db, *_ = ctx
    assert c.get("/products/kunafa", headers=GW).json()["nombre"] == "Kunafa"
    assert c.get(f"/products/{pid(db, 'kunafa')}", headers=GW).json()["slug"] == "kunafa"
    assert c.get("/products/no-existe", headers=GW).status_code == 404


def test_administracion_solo_admin(ctx):
    c, db, *_ = ctx
    nuevo = {"slug": "te-menta", "nombre": "Té de menta", "categoria": "postres", "precio": 2500, "stock": 10}
    assert c.post("/products", headers=GW, json=nuevo).status_code == 401           # sin identidad
    assert c.post("/products", headers=as_("cliente"), json=nuevo).status_code == 403
    assert c.post("/products", headers=as_("cajero"), json=nuevo).status_code == 403
    assert c.post("/products", headers=as_("administrador", aud="orders"), json=nuevo).status_code == 401  # token de otro destino
    r = c.post("/products", headers=as_("administrador"), json=nuevo)
    assert r.status_code == 201 and r.json()["stock"] == 10
    assert c.post("/products", headers=as_("administrador"), json=nuevo).status_code == 409
    assert c.post("/products", headers=as_("administrador"), json=nuevo | {"slug": "x", "precio": -5}).status_code == 422
    assert c.post("/products", headers=as_("administrador"), json=nuevo | {"slug": "y", "categoria": "bebidas"}).status_code == 400


def test_put_reemplaza_y_delete_es_baja_logica(ctx):
    c, db, *_ = ctx
    base = {"slug": "kunafa", "nombre": "Kunafa Real", "categoria": "postres", "precio": 6500}
    assert c.put("/products/kunafa", headers=as_("administrador"), json=base).json()["precio"] == 6500
    assert c.delete("/products/kunafa", headers=as_("cliente")).status_code == 403
    assert c.delete("/products/kunafa", headers=as_("administrador")).status_code == 204
    assert c.get("/products/kunafa", headers=GW).status_code == 404
    assert "kunafa" not in [p["slug"] for p in c.get("/products", headers=GW).json()]
    assert db.products.find_one({"slug": "kunafa"})["activo"] is False  # el registro se conserva


def test_disponibilidad_cajero_si_cliente_no(ctx):
    c, *_ = ctx
    assert c.patch("/products/baklava/availability", headers=as_("cliente"), json={"disponible": False}).status_code == 403
    r = c.patch("/products/baklava/availability", headers=as_("cajero"), json={"disponible": False, "stock": 3})
    assert r.status_code == 200 and r.json()["disponible"] is False and r.json()["stock"] == 3


def test_reserva_calcula_precio_en_el_servidor_y_descuenta(ctx):
    c, db, *_ = ctx
    body = {"orderId": "o1", "items": [{"productId": pid(db, "kebab-mixto"), "cantidad": 2}], "precio": 1, "total": 1}
    r = c.post("/internal/reserve", headers=ORD, json=body)
    assert r.status_code == 200
    assert r.json()["items"][0]["precioUnitario"] == 13990 and r.json()["total"] == 27980  # ignora el precio enviado
    assert db.products.find_one({"slug": "kebab-mixto"})["stock"] == 48


def test_reserva_idempotente(ctx):
    c, db, *_ = ctx
    body = {"orderId": "o1", "items": [{"productId": pid(db, "baklava"), "cantidad": 5}]}
    a, b = c.post("/internal/reserve", headers=ORD, json=body), c.post("/internal/reserve", headers=ORD, json=body)
    assert a.json() == b.json() and db.products.find_one({"slug": "baklava"})["stock"] == 45


def test_reserva_todo_o_nada_y_sin_sobreventa(ctx):
    c, db, *_ = ctx
    db.products.update_one({"slug": "baklava"}, {"$set": {"stock": 5}})
    ok = c.post("/internal/reserve", headers=ORD, json={"orderId": "A", "items": [{"productId": pid(db, "baklava"), "cantidad": 3}]})
    ko = c.post("/internal/reserve", headers=ORD, json={"orderId": "B", "items": [
        {"productId": pid(db, "kunafa"), "cantidad": 2}, {"productId": pid(db, "baklava"), "cantidad": 3}]})
    assert ok.status_code == 200 and ko.status_code == 409
    assert db.products.find_one({"slug": "baklava"})["stock"] == 2
    assert db.products.find_one({"slug": "kunafa"})["stock"] == 50  # lo descontado antes del fallo se revirtió
    # el pedido B puede reintentarse con otro carrito
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "B", "items": [{"productId": pid(db, "baklava"), "cantidad": 2}]}).status_code == 200


def test_reserva_rechaza_no_disponible_inexistente_y_repetidos(ctx):
    c, db, *_ = ctx
    db.products.update_one({"slug": "tabbouleh"}, {"$set": {"disponible": False}})
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "a", "items": [{"productId": pid(db, "tabbouleh"), "cantidad": 1}]}).status_code == 409
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "b", "items": [{"productId": "0" * 24, "cantidad": 1}]}).status_code == 409
    dup = {"productId": pid(db, "baklava"), "cantidad": 1}
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "c", "items": [dup, dup]}).status_code == 400
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "d", "items": [dup | {"cantidad": 0}]}).status_code == 422


def test_release_devuelve_stock_una_sola_vez(ctx):
    c, db, *_ = ctx
    c.post("/internal/reserve", headers=ORD, json={"orderId": "o9", "items": [{"productId": pid(db, "falafel-casero"), "cantidad": 4}]})
    assert db.products.find_one({"slug": "falafel-casero"})["stock"] == 46
    assert c.post("/internal/release", headers=ORD, json={"orderId": "o9"}).status_code == 200
    assert c.post("/internal/release", headers=ORD, json={"orderId": "o9"}).status_code == 200
    assert db.products.find_one({"slug": "falafel-casero"})["stock"] == 50
    assert c.post("/internal/release", headers=ORD, json={"orderId": "nunca"}).status_code == 404


def test_promocion_vigente_se_aplica_al_precio(ctx):
    c, db, *_ = ctx
    db.promotions.delete_many({})
    db.promotions.insert_one({"titulo": "t", "descuentoPct": 15, "vigenciaDesde": "2000-01-01", "vigenciaHasta": "2999-12-31",
                              "productIds": [db.products.find_one({"slug": "baklava"})["_id"]]})
    r = c.post("/internal/reserve", headers=ORD, json={"orderId": "p", "items": [{"productId": pid(db, "baklava"), "cantidad": 1}]})
    assert r.json()["items"][0]["precioUnitario"] == 4242
    assert len(c.get("/promotions", headers=GW).json()) == 1
    db.promotions.update_many({}, {"$set": {"vigenciaHasta": "2001-01-01"}})
    assert c.get("/promotions", headers=GW).json() == []


def test_reserva_acepta_slug_y_devuelve_el_id(ctx):
    c, db, *_ = ctx
    r = c.post("/internal/reserve", headers=ORD, json={"orderId": "s1", "items": [{"productId": "kunafa", "cantidad": 2}]})
    assert r.status_code == 200 and r.json()["items"][0]["productId"] == pid(db, "kunafa")
    # el mismo producto por slug e id cuenta como repetido
    dup = [{"productId": "baklava", "cantidad": 1}, {"productId": pid(db, "baklava"), "cantidad": 1}]
    assert c.post("/internal/reserve", headers=ORD, json={"orderId": "s2", "items": dup}).status_code == 400


def test_vista_admin_incluye_baja_y_stock(ctx):
    c, db, *_ = ctx
    c.delete("/products/kunafa", headers=as_("administrador"))
    assert c.get("/admin/products", headers=as_("cliente")).status_code == 403
    assert c.get("/admin/products", headers=GW).status_code == 401
    lista = c.get("/admin/products", headers=as_("cajero")).json()
    assert len(lista) == 12 and all("stock" in p and "activo" in p for p in lista)
    assert [p for p in lista if p["slug"] == "kunafa"][0]["activo"] is False
    assert all("stock" not in p for p in c.get("/products", headers=GW).json())  # lo público sigue sin stock


def _reserva_a_medias(db, minutos):
    """Simula un proceso que murió tras descontar 4 unidades de baklava y anotarlo."""
    from datetime import timedelta
    inv = sys.modules["inventory_main"] if "inventory_main" in sys.modules else load("inventory_main", ROOT / "svc-inventory" / "main.py")
    db.products.update_one({"slug": "baklava"}, {"$inc": {"stock": -4}})
    db.reservations.insert_one({"_id": "muerta", "state": "pending", "created_at": inv.now() - timedelta(minutes=minutos),
                                "restock": [[str(db.products.find_one({"slug": "baklava"})["_id"]), 4]]})
    return inv


def test_barrido_devuelve_stock_de_reservas_a_medias(ctx):
    c, db, *_ = ctx
    inv = _reserva_a_medias(db, minutos=10)
    assert db.products.find_one({"slug": "baklava"})["stock"] == 46
    assert inv.sweep_stale(db) == 1
    assert db.products.find_one({"slug": "baklava"})["stock"] == 50
    assert inv.sweep_stale(db) == 0 and db.products.find_one({"slug": "baklava"})["stock"] == 50  # no devuelve dos veces
    # la reserva expirada no se puede reanudar con el mismo orderId
    r = c.post("/internal/reserve", headers=ORD, json={"orderId": "muerta", "items": [{"productId": "baklava", "cantidad": 1}]})
    assert r.status_code == 409


def test_barrido_no_toca_reservas_recientes(ctx):
    c, db, *_ = ctx
    inv = _reserva_a_medias(db, minutos=0)
    assert inv.sweep_stale(db) == 0 and db.products.find_one({"slug": "baklava"})["stock"] == 46


GQL = {"X-Caller": "graphql-gateway", "X-Caller-Key": "valor-gql-inventory"}


def test_consulta_por_lote_de_slugs(ctx):
    c, db, *_ = ctx
    r = c.get("/products?slugs=baklava,kunafa,no-existe", headers=GQL)
    assert r.status_code == 200 and sorted(p["slug"] for p in r.json()) == ["baklava", "kunafa"]
    assert c.get("/products?slugs=", headers=GW).status_code == 400
    assert c.get("/products?slugs=" + ",".join(f"p{i}" for i in range(31)), headers=GW).status_code == 400
    assert c.get("/products?slugs=Mal_Slug;drop", headers=GW).status_code == 400
    db.products.update_one({"slug": "kunafa"}, {"$set": {"activo": False}})
    assert [p["slug"] for p in c.get("/products?slugs=kunafa,baklava", headers=GW).json()] == ["baklava"]   # los dados de baja no salen


def test_graphql_gateway_solo_lee_el_catalogo_publico(ctx):
    c, *_ = ctx
    assert c.get("/products", headers=GQL).status_code == 200
    nuevo = {"slug": "te-menta", "nombre": "Té de menta", "categoria": "postres", "precio": 2500}
    assert c.post("/products", headers=GQL | {"X-Internal-Identity": as_("administrador")["X-Internal-Identity"]}, json=nuevo).status_code == 403
    assert c.post("/internal/reserve", headers=GQL, json={"orderId": "o1", "items": []}).status_code == 403
    assert c.get("/products", headers=GQL | {"X-Caller-Key": "valor-gw-inventory"}).status_code == 401   # la clave del gateway no sirve en el tramo GraphQL
