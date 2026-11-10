"""Datos de prueba para Al Sahara, creados a traves del gateway (solo libreria estandar).

Todo pasa por las mismas reglas que un usuario real: hashes en auth, stock atomico en inventory, pago aprobado en la
pasarela simulada (que firma el webhook ella misma), boleta correlativa y correos en mail-outbox/outbox.jsonl.
Es idempotente: si lo corres dos veces no duplica clientes, y solo crea los pedidos y reservas que falten.

Uso (PowerShell, desde la carpeta Evaluacion2, con el sistema levantado):
  $env:CAJERO_EMAIL="cajero@alsahara.cl"; $env:CAJERO_PASS="<SEED_CAJERO_PASSWORD de secrets/seed.env>"
  python scripts\\seed_test_data.py --clientes 30 --pedidos 80 --reservas 15

Clientes creados: cliente01@example.cl ... con clave Prueba1234 (datos ficticios, RUN validos inventados).
Si aparece 429 (limite de solicitudes), sube la pausa:  $env:PAUSA="0.5"
"""
import argparse, http.cookiejar, json, os, random, re, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta

BASE = os.getenv("BASE_URL", "http://localhost:8000/api/v1")
ORIGIN = os.getenv("ORIGIN", "http://localhost:8080")          # debe estar en ALLOWED_ORIGINS del gateway
PROVIDER = os.getenv("PROVIDER_URL", "http://localhost:9000")  # pasarela simulada
OUTBOX = os.getenv("OUTBOX", os.path.join("mail-outbox", "outbox.jsonl"))
PAUSA = float(os.getenv("PAUSA", "0.1"))
CLAVE = "Prueba1234"
MARCA = "[seed]"  # prefijo del comentario de los pedidos creados por este script
COMUNA_OK = "Viña del Mar"  # unica comuna con cobertura en svc-orders/coverage.json
SLUGS = ["hummus-tradicional", "baba-ganoush", "fatayer-espinaca", "shawarma-cordero", "kebab-mixto", "kafta-al-sahara",
         "falafel-casero", "tabbouleh", "fatteh-garbanzos", "baklava", "kunafa", "muhallabia"]
NOMBRES = ["Camila", "Matías", "Valentina", "Benjamín", "Isidora", "Vicente", "Florencia", "Tomás", "Antonia", "Joaquín",
           "Martina", "Agustín", "Sofía", "Cristóbal", "Josefa", "Lucas", "Catalina", "Diego", "Javiera", "Felipe"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores", "Espinoza", "Valenzuela"]
CALLES = ["Av. Libertad", "Calle Valparaíso", "Av. San Martín", "Calle Quillota", "Av. Perú", "Calle Arlegui", "Av. Marina"]
CONDUCTORES = ["Pedro Ruiz", "Ana Vega", "Luis Castro"]


# ------------------------------------------------------------------ HTTP
class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # la pasarela redirige al frontend; no hace falta seguirla


class Sesion:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, metodo, ruta, cuerpo=None, ok=(200, 201, 204)):
        """Devuelve (codigo, json). Reintenta si el gateway responde 429."""
        for intento in range(6):
            datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
            req = urllib.request.Request(BASE + ruta, data=datos, method=metodo,
                                         headers={"Content-Type": "application/json", "Origin": ORIGIN})
            try:
                with self.op.open(req, timeout=15) as r:
                    texto = r.read().decode() or "null"
                    codigo = r.status
            except urllib.error.HTTPError as e:
                codigo, texto = e.code, e.read().decode() or "null"
                if codigo == 429:
                    espera = int(e.headers.get("Retry-After", "5"))
                    print(f"   429 en {ruta}: espero {espera}s")
                    time.sleep(espera)
                    continue
            time.sleep(PAUSA)
            try:
                return codigo, json.loads(texto)
            except ValueError:
                return codigo, texto
        return 429, None


def login(email, clave):
    s = Sesion()
    codigo, r = s.call("POST", "/auth/login", {"email": email, "password": clave})
    if codigo != 200:
        sys.exit(f"Login fallido para {email}: {codigo} {r}")
    print(f"Sesion iniciada: {email} (rol {r['role']})")
    return s


# ------------------------------------------------------------------ datos ficticios
def dv(numero: int) -> str:
    total, mult = 0, 2
    for d in reversed(str(numero)):
        total += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    r = 11 - total % 11
    return "0" if r == 11 else "K" if r == 10 else str(r)


def run_ficticio(i: int) -> str:
    n = 30_000_000 + i * 7919  # rango fijo: siempre el mismo RUN para el mismo indice (idempotencia)
    return f"{n}-{dv(n)}"


def cliente_ficticio(i: int) -> dict:
    rnd = random.Random(i)
    nacimiento = date(1960, 1, 1) + timedelta(days=rnd.randint(0, 15000))
    return {"run": run_ficticio(i), "nombre": f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)}",
            "fechaNacimiento": nacimiento.isoformat(), "sexo": rnd.choice("FMO"),
            "telefono": f"+569{rnd.randint(10_000_000, 99_999_999)}", "email": f"cliente{i:02d}@example.cl",
            "password": CLAVE, "direccion": f"{rnd.choice(CALLES)} {rnd.randint(100, 2999)}",
            "comuna": COMUNA_OK, "provincia": "Valparaíso", "region": "Valparaíso"}


def token_verificacion(email):
    """Busca en el outbox el ultimo correo de verificacion enviado a ese correo."""
    try:
        with open(OUTBOX, encoding="utf-8") as f:
            lineas = [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return None
    for m in reversed(lineas):
        if m.get("to") == email:
            hallado = re.search(r"token=([A-Za-z0-9_-]+)", m.get("body", ""))
            if hallado:
                return hallado.group(1)
    return None


# ------------------------------------------------------------------ pasos
def crear_clientes(staff, n):
    anon, ids = Sesion(), []
    for i in range(1, n + 1):
        c = cliente_ficticio(i)
        codigo, r = anon.call("POST", "/auth/register", c)
        if codigo == 201:
            time.sleep(0.3)  # el correo de verificacion se escribe de forma asincrona
            token = token_verificacion(c["email"])
            if token:
                anon.call("POST", "/auth/verify-email", {"token": token})
            else:
                print(f"   aviso: no encontre el correo de verificacion de {c['email']} en {OUTBOX}")
        elif codigo != 409:
            print(f"   registro {c['email']}: {codigo} {r}")
            continue
        codigo, lista = staff.call("GET", "/clients?" + urllib.parse.urlencode({"q": c["run"]}))
        if codigo == 200 and lista:
            ids.append(lista[0]["id"])
    print(f"Clientes listos: {len(ids)} (cliente01..{n:02d}@example.cl / {CLAVE})")
    return ids


def pedidos_existentes(staff):
    total, page = 0, 1
    while True:
        codigo, lote = staff.call("GET", f"/orders?page={page}&limit=100")
        if codigo != 200 or not lote:
            return total
        total += sum(1 for o in lote if (o.get("comentario") or "").startswith(MARCA))
        if len(lote) < 100:
            return total
        page += 1


def pagar(staff, order_id, aprobar=True):
    codigo, r = staff.call("POST", "/payments", {"orderId": order_id})
    if codigo != 201:
        print(f"   pago {order_id}: {codigo} {r}")
        return False
    token = urllib.parse.parse_qs(urllib.parse.urlparse(r["checkoutUrl"]).query)["t"][0]
    form = urllib.parse.urlencode({"t": token, "resultado": "ok" if aprobar else "fail"}).encode()
    try:
        urllib.request.build_opener(SinRedireccion).open(
            urllib.request.Request(PROVIDER + "/pay/result", data=form, method="POST",
                                   headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=15)
    except urllib.error.HTTPError as e:
        if e.code not in (302, 303):
            print(f"   pasarela {order_id}: {e.code}")
            return False
    if not aprobar:
        return True
    for _ in range(20):  # orders recibe el evento pago.aprobado por ActiveMQ
        codigo, o = staff.call("GET", f"/orders/{order_id}")
        if codigo == 200 and o["estado"] == "PAGADO":
            return True
        time.sleep(0.5)
    print(f"   aviso: {order_id} no paso a PAGADO (revisa payments/orders con docker compose logs)")
    return False


def avanzar(staff, order_id, *estados):
    for e in estados:
        codigo, r = staff.call("PATCH", f"/orders/{order_id}/status", {"estado": e})
        if codigo != 200:
            print(f"   estado {e} en {order_id}: {codigo} {r}")
            return False
    return True


def crear_pedidos(staff, clientes, n, pagar_pedidos):
    ya = pedidos_existentes(staff)
    faltan = max(0, n - ya)
    print(f"Pedidos de prueba existentes: {ya}; creo {faltan}")
    rnd = random.Random(42 + ya)
    resumen = {}
    for k in range(faltan):
        tipo = "LOCAL" if k % 4 == 0 else "DELIVERY"  # 1 de cada 4 es venta en local (RF4)
        cuerpo = {"items": [{"slug": s, "cantidad": rnd.randint(1, 2)} for s in rnd.sample(SLUGS, rnd.randint(1, 3))],
                  "tipo": tipo, "clienteId": rnd.choice(clientes), "comentario": f"{MARCA} pedido {ya + k + 1}"}
        if tipo == "DELIVERY":
            cuerpo |= {"direccion": f"{rnd.choice(CALLES)} {rnd.randint(100, 2999)}", "comuna": COMUNA_OK}
        codigo, o = staff.call("POST", "/orders", cuerpo)
        if codigo != 201:
            print(f"   pedido: {codigo} {o}")
            if codigo == 422 and "stock" in str(o).lower():
                print("   sin stock: reponlo como admin (PATCH /products/{slug}/availability con stock) y repite")
                break
            continue
        oid = o["id"]
        destino = rnd.random()
        if not pagar_pedidos or destino < 0.15:
            final = "CREADO (se anula solo a los 30 min)"
        elif destino < 0.25:
            pagar(staff, oid, aprobar=False)
            final = "pago rechazado"
        elif destino < 0.35:
            staff.call("POST", f"/orders/{oid}/cancel", {"motivo": "Cliente se arrepintió de la compra"})
            final = "CANCELADO"
        elif not pagar(staff, oid):
            final = "pago sin confirmar"
        elif destino < 0.50:
            final = "PAGADO"
        elif destino < 0.65:
            avanzar(staff, oid, "EN_PREPARACION")
            final = "EN_PREPARACION"
        elif tipo == "LOCAL":
            avanzar(staff, oid, "EN_PREPARACION", "LISTO", "ENTREGADO")
            final = "ENTREGADO (local)"
        elif avanzar(staff, oid, "EN_PREPARACION", "LISTO"):
            codigo, _ = staff.call("PATCH", f"/dispatch/{oid}", {"estado": "EN_CAMINO", "conductor": rnd.choice(CONDUCTORES)})
            final = "EN_CAMINO"
            if codigo == 200 and destino > 0.85:
                staff.call("PATCH", f"/dispatch/{oid}", {"estado": "ENTREGADO"})
                final = "ENTREGADO (delivery)"
        else:
            final = "error al avanzar"
        resumen[final] = resumen.get(final, 0) + 1
        print(f"   {ya + k + 1:3}. {tipo:8} {o['total']:>7} -> {final}")
    if resumen:
        print("Resumen de pedidos:", json.dumps(resumen, ensure_ascii=False))


def crear_reservas(staff, n):
    codigo, existentes = staff.call("GET", "/reservations?limit=100")
    ya = sum(1 for r in existentes if (r.get("mensaje") or "").startswith(MARCA)) if codigo == 200 else 0
    anon, rnd = Sesion(), random.Random(7 + ya)
    creadas = 0
    for k in range(max(0, n - ya)):
        cuando = (datetime.now() + timedelta(days=rnd.randint(1, 60))).replace(hour=rnd.choice([13, 14, 20, 21]), minute=0,
                                                                                 second=0, microsecond=0)
        cuerpo = {"nombre": f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)}", "email": f"reserva{ya + k + 1:02d}@example.cl",
                  "personas": rnd.randint(2, 8), "fechaHora": cuando.isoformat(timespec="minutes"),
                  "mensaje": f"{MARCA} reserva de prueba"}
        codigo, r = anon.call("POST", "/reservations", cuerpo)
        if codigo != 201:
            print(f"   reserva: {codigo} {r}")
            continue
        creadas += 1
        decision = rnd.random()
        if decision < 0.5:
            staff.call("PATCH", f"/reservations/{r['id']}", {"estado": "CONFIRMADA"})
        elif decision < 0.7:
            staff.call("PATCH", f"/reservations/{r['id']}", {"estado": "RECHAZADA"})
    print(f"Reservas: {ya} existentes, {creadas} nuevas (las demas quedan PENDIENTE)")


def ids_para_evidencias(staff):
    print("\nIds utiles para evidencias_faltantes.ps1:")
    for estado in ("LISTO", "EN_CAMINO", "PAGADO", "CREADO"):
        codigo, lote = staff.call("GET", f"/orders?estado={estado}&limit=1")
        if codigo == 200 and lote:
            print(f"   pedido {estado:10} {lote[0]['id']}  (tipo {lote[0]['tipo']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clientes", type=int, default=30)
    ap.add_argument("--pedidos", type=int, default=80)
    ap.add_argument("--reservas", type=int, default=15)
    ap.add_argument("--sin-pagar", action="store_true", help="no aprueba pagos (los pedidos quedan CREADO)")
    a = ap.parse_args()
    if not (os.getenv("CAJERO_EMAIL") and os.getenv("CAJERO_PASS")):
        sys.exit("Define CAJERO_EMAIL y CAJERO_PASS (ver secrets/seed.env).")
    cajero = login(os.environ["CAJERO_EMAIL"], os.environ["CAJERO_PASS"])
    clientes = crear_clientes(cajero, a.clientes)
    if not clientes:
        sys.exit("No hay clientes: revisa los errores de registro de arriba.")
    crear_pedidos(cajero, clientes, a.pedidos, not a.sin_pagar)
    crear_reservas(cajero, a.reservas)
    ids_para_evidencias(cajero)
