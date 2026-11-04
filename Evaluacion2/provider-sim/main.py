"""Proveedor de pagos SIMULADO (solo para pruebas y demo). Hace de pasarela externa: muestra una página de pago, y al
aprobar o rechazar avisa al backend mediante un webhook firmado con HMAC, igual que un proveedor real. Está fuera de la red
privada: solo conoce el secreto compartido del webhook (variable de entorno) y la URL pública del gateway.
El navegador nunca le dice al backend que el pago salió bien: lo dice este servicio, con firma."""
import html, json, os, time, uuid
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from shared import signing

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8000").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")

app = FastAPI(title="provider-sim", docs_url=None, redoc_url=None, openapi_url=None)

PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pasarela de pago (simulada)</title>
<style>body{{font-family:system-ui,sans-serif;background:#f6f1e7;display:grid;place-items:center;min-height:100vh;margin:0}}
.c{{background:#fff;border-radius:12px;padding:2rem;max-width:420px;width:calc(100% - 2rem);box-shadow:0 4px 18px #0002}}
button{{padding:.7rem 1.2rem;border:0;border-radius:8px;font-size:1rem;cursor:pointer;margin:.25rem 0;width:100%}}
.ok{{background:#2e7d32;color:#fff}}.no{{background:#eee}}small{{color:#666}}</style></head><body><div class="c">
<h1 style="margin-top:0">Pasarela de pago</h1><p><small>Entorno de pruebas: no se cobra dinero real.</small></p>
<p>Pedido <b>{order}</b><br>Monto: <b>${amount}</b></p>
<form method="post" action="/pay/result"><input type="hidden" name="t" value="{token}">
<button class="ok" name="resultado" value="ok">Pagar (aprobar)</button>
<button class="no" name="resultado" value="fail">Rechazar el pago</button></form></div></body></html>"""


def secrets_list():
    return [WEBHOOK_SECRET] if WEBHOOK_SECRET else []


def error(msg, status=400):
    return HTMLResponse(f"<p>{html.escape(msg)}</p>", status_code=status)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/pay", response_class=HTMLResponse)
def pay_page(t: str = ""):
    claims = signing.read_token(secrets_list(), t)
    if not claims:
        return error("Enlace de pago inválido o vencido.")
    return PAGE.format(order=html.escape(str(claims["order"])), amount=f"{int(claims['amount']):,}".replace(",", "."), token=html.escape(t, quote=True))


@app.post("/pay/result")
async def pay_result(request: Request):
    form = parse_qs((await request.body()).decode(), keep_blank_values=True)
    token, resultado = form.get("t", [""])[0], form.get("resultado", [""])[0]
    claims = signing.read_token(secrets_list(), token)
    if not claims or resultado not in ("ok", "fail"):
        return error("Solicitud inválida o enlace vencido.")
    event = {"event_id": uuid.uuid4().hex, "type": "payment.succeeded" if resultado == "ok" else "payment.failed",
             "provider_ref": claims["ref"], "amount": claims["amount"], "ts": int(time.time())}
    raw = json.dumps(event, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "X-Signature": "sha256=" + signing.sign_bytes(WEBHOOK_SECRET, raw)}
    try:
        httpx.post(f"{GATEWAY_URL}/api/v1/webhooks/payments", content=raw, headers=headers, timeout=5)
    except httpx.HTTPError:
        return error("No se pudo avisar al comercio. Intenta nuevamente.", 502)
    ret = claims["ret"]
    if not ret.startswith(FRONTEND_URL + "/"):  # evita redirecciones abiertas
        return error("Pago procesado. Puedes cerrar esta ventana.")
    return RedirectResponse(f"{ret}&estado={'ok' if resultado == 'ok' else 'fail'}", status_code=303)
