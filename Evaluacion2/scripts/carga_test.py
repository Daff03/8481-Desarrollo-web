"""Prueba de carga simple para Al Sahara (solo libreria estandar).

IMPORTANTE: el gateway limita a RATE_LIMIT_PER_MIN solicitudes por minuto, por IP y por ruta (300 por defecto).
Desde un solo equipo esa cuota se agota en el primer segundo y el resto serian 429. Antes de medir:
  1. En Evaluacion2/.env:  RATE_LIMIT_PER_MIN=1000000
  2. docker compose up -d gateway
  3. Al terminar, volver al valor original y repetir el paso 2. Declararlo en el informe.

Uso (PowerShell, desde Evaluacion2):
  $env:ADMIN_EMAIL="admin@alsahara.cl"; $env:ADMIN_PASS="<de secrets/seed.env>"
  python scripts\\carga_test.py --hilos 50 --segundos 30
En otra terminal, durante la prueba:
  docker stats --no-stream      (capturar CPU y memoria)
"""
import argparse, collections, http.cookiejar, json, os, statistics, threading, time
import urllib.parse, urllib.request, urllib.error

BASE = os.getenv("BASE_URL", "http://localhost:8000/api/v1")
ORIGIN = os.getenv("ORIGIN", "http://localhost:8080")  # debe estar en ALLOWED_ORIGINS del gateway


def abrir():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def login_admin():
    op = abrir()
    body = json.dumps({"email": os.environ["ADMIN_EMAIL"],
                       "password": os.environ["ADMIN_PASS"]}).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Origin": ORIGIN})
    op.open(req, timeout=10).read()
    return op


def pct(datos, p):
    if not datos:
        return 0.0
    return datos[min(len(datos) - 1, int(round(p / 100 * len(datos))) - 1)]


def correr(nombre, ruta, hilos, segundos, opener=None):
    lat_ok, codigos, lock = [], collections.Counter(), threading.Lock()
    fin = time.time() + segundos

    def worker():
        op = opener or abrir()
        while time.time() < fin:
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request(BASE + ruta, headers={"Origin": ORIGIN})
                with op.open(req, timeout=10) as r:
                    r.read()
                    codigo = r.status
            except urllib.error.HTTPError as e:
                codigo = e.code
            except Exception:
                codigo = "red/timeout"
            dt = (time.perf_counter() - t0) * 1000
            with lock:
                codigos[codigo] += 1
                if codigo == 200:
                    lat_ok.append(dt)  # solo respuestas validas: un 429 rapido no debe mejorar el p95

    ts = [threading.Thread(target=worker) for _ in range(hilos)]
    t0 = time.time()
    [t.start() for t in ts]
    [t.join() for t in ts]
    dur = time.time() - t0
    lat_ok.sort()
    total = sum(codigos.values())
    errores = total - codigos.get(200, 0)
    p50 = statistics.median(lat_ok) if lat_ok else 0.0
    print(f"{nombre:24} hilos={hilos:3} dur={dur:5.1f}s req={total:6} ok/s={len(lat_ok)/dur:7.1f} "
          f"p50={p50:6.1f}ms p95={pct(lat_ok, 95):6.1f}ms errores={errores} ({100*errores/max(total,1):.1f}%)")
    print(f"{'':24} codigos: {dict(codigos)}")
    if codigos.get(429):
        print(f"{'':24} AVISO: hubo 429; sube RATE_LIMIT_PER_MIN (ver cabecera del script) y repite.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hilos", type=int, default=50)
    ap.add_argument("--segundos", type=int, default=30)
    ap.add_argument("--comuna", default="Viña del Mar")  # comuna con cobertura en coverage.json
    a = ap.parse_args()

    correr("GET /products", "/products", a.hilos, a.segundos)
    correr("GET /delivery/coverage", "/delivery/coverage?comuna=" + urllib.parse.quote(a.comuna), a.hilos, a.segundos)
    if os.getenv("ADMIN_EMAIL"):
        adm = login_admin()  # una sola sesion compartida: el gateway limita los logins a LOGIN_RATE_PER_MIN
        correr("GET /reports/sales", "/reports/sales?desde=2026-10-01&hasta=2026-11-09",
               min(a.hilos, 10), a.segundos, opener=adm)
    else:
        print("GET /reports/sales omitido: define ADMIN_EMAIL y ADMIN_PASS.")
