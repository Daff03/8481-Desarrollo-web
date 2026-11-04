"""notifier: consume `notificaciones.correo` de ActiveMQ y envía los correos (verificación, boleta, reservas).
Adaptador de pruebas: en vez de SMTP escribe cada correo en un archivo JSONL (MAIL_OUTBOX), conservando el contrato
del mensaje. Para producción bastaría otro `Sender` con SMTP. No expone nada salvo /health y no guarda datos propios."""
import json, logging, os, re, threading, time
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from shared.events import EventBus

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080").rstrip("/")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("notifier")


def clp(n) -> str:
    return "$" + f"{int(n):,}".replace(",", ".")


# plantilla → (campos obligatorios de data, función que arma asunto y cuerpo)
def _verificar(d):
    return ("Confirma tu correo en Al Sahara",
            f"Hola,\n\nPara activar tu cuenta abre este enlace:\n{FRONTEND_URL}/verificar.php?token={d['token']}\n\n"
            "El enlace vence en 24 horas. Si no creaste una cuenta, ignora este mensaje.\n\nAl Sahara")


def _boleta(d):
    lineas = "\n".join(f"  {i['cantidad']} x {i['nombre']}  {clp(i['subtotal'])}" for i in d["items"])
    return (f"Boleta N° {d['numero']} - Al Sahara",
            f"Hola {d['nombre']},\n\nGracias por tu compra. Boleta N° {d['numero']}\n\n{lineas}\n\nTotal: {clp(d['total'])}\n\nAl Sahara")


def _reserva(d):
    estado = {"PENDIENTE": "recibida; te confirmaremos pronto", "CONFIRMADA": "confirmada", "RECHAZADA": "rechazada", "CANCELADA": "cancelada"}[d["estado"]]
    return (f"Tu reserva en Al Sahara está {d['estado'].lower()}",
            f"Hola {d['nombre']},\n\nTu reserva para {d['personas']} persona(s) el {d['fechaHora']} fue {estado}.\n\nAl Sahara")


TEMPLATES = {"verificar_correo": ({"token"}, _verificar),
             "boleta": ({"numero", "nombre", "items", "total"}, _boleta),
             "reserva": ({"estado", "nombre", "personas", "fechaHora"}, _reserva)}


class FileSender:
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()

    def send(self, to, subject, body):
        line = json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "to": to, "subject": subject, "body": body}, ensure_ascii=False)
        with self.lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


class Notifier:
    def __init__(self, sender, remember=2000):
        self.sender, self.seen, self.remember = sender, OrderedDict(), remember

    def handle(self, payload: dict, event_id: str):
        """Lanza ValueError si el mensaje es inválido (el broker lo manda a DLQ). Los duplicados recientes se ignoran."""
        if event_id in self.seen:
            return
        to, name = payload["to"], payload["template"]
        if not EMAIL_RE.match(str(to)):
            raise ValueError("Destinatario inválido")
        if name not in TEMPLATES:
            raise ValueError("Plantilla desconocida")
        required, render = TEMPLATES[name]
        data = payload["data"]
        if not isinstance(data, dict) or required - set(data):
            raise ValueError("Datos incompletos")
        subject, body = render(data)
        self.sender.send(to, subject, body)
        self.seen[event_id] = True
        if len(self.seen) > self.remember:
            self.seen.popitem(last=False)
        log.info(json.dumps({"event": "mail_sent", "template": name, "event_id": event_id}))  # sin destinatario ni contenido


def run_consumer(bus: EventBus, notifier: Notifier, stop: threading.Event, retry_seconds=5):
    """Mantiene la suscripción; si el broker cae, reintenta. Los mensajes persistentes esperan en la cola."""
    while not stop.is_set():
        try:
            conn = bus.consume("correo.enviar", notifier.handle)
            while conn.is_connected() and not stop.is_set():
                time.sleep(1)
            if conn.is_connected():
                conn.disconnect()
        except Exception as exc:
            log.warning(json.dumps({"event": "broker_unavailable", "error": type(exc).__name__}))
        stop.wait(retry_seconds)


_stop = threading.Event()


@asynccontextmanager
async def lifespan(app):
    thread = None
    if os.environ.get("START_CONSUMER", "false").lower() == "true":
        from shared.secret_provider import SecretProvider
        notifier = Notifier(FileSender(os.environ.get("MAIL_OUTBOX", "/mail/outbox.jsonl")))
        thread = threading.Thread(target=run_consumer, args=(EventBus(SecretProvider(), "notifier"), notifier, _stop), daemon=True)
        thread.start()
    yield
    _stop.set()


app = FastAPI(title="notifier", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
