"""Eventos entre servicios por ActiveMQ (STOMP, como en la Semana_10). Colas persistentes con ack individual.
Cada servicio entra al broker con su propio usuario (referencia mq-<servicio>) y solo puede leer/escribir las colas
que permite activemq/queues.json. Los mensajes son JSON con campos mínimos: nunca contraseñas ni tokens.
La idempotencia es responsabilidad del consumidor (clave: event_id)."""
import json, logging, os, time, uuid

log = logging.getLogger("events")
MAX_BYTES = 64_000

# tipo de evento → (cola, campos obligatorios del payload)
EVENTS = {
    "pago.aprobado":   ("/queue/pagos.aprobados",       {"order_id", "amount", "provider_ref"}),
    "correo.enviar":   ("/queue/notificaciones.correo", {"to", "template", "data"}),
}


class EventBusUnavailable(Exception):
    """El broker no responde: quien publica debe reintentar (por ejemplo con un outbox en su base)."""


class InvalidEvent(Exception):
    pass


def _validate(event_type: str, payload: dict):
    if event_type not in EVENTS:
        raise InvalidEvent(f"Tipo de evento desconocido: {event_type}")
    missing = EVENTS[event_type][1] - set(payload)
    if missing:
        raise InvalidEvent(f"Faltan campos: {sorted(missing)}")


def _default_connection(host, port):
    import stomp  # stomp.py; se importa aquí para que las pruebas no lo necesiten
    return stomp.Connection12([(host, port)], vhost="/", heartbeats=(10000, 10000))


class EventBus:
    def __init__(self, provider, user: str, host=None, port=None, connection_factory=None):
        self.provider, self.user = provider, user
        self.host = host or os.environ.get("BROKER_HOST", "activemq")
        self.port = int(port or os.environ.get("BROKER_PORT", "61613"))
        self.factory = connection_factory or _default_connection

    def _connect(self, listener=None):
        conn = self.factory(self.host, self.port)
        if listener:
            conn.set_listener("bus", listener)
        try:
            secret = self.provider.get(f"mq-{self.user}")["current"]
            conn.connect(self.user, secret, wait=True)
        except Exception as exc:  # broker caído, credencial rechazada o gestor de secretos caído
            raise EventBusUnavailable("No se pudo conectar con el broker") from exc
        return conn

    def publish(self, event_type: str, payload: dict, event_id: str | None = None, correlation_id: str | None = None) -> str:
        """Publica un mensaje persistente. Devuelve el event_id (se reutiliza al reintentar para que el consumidor deduplique)."""
        _validate(event_type, payload)
        event_id = event_id or uuid.uuid4().hex
        body = json.dumps({"event_id": event_id, "type": event_type, "ts": int(time.time()), "payload": payload}, ensure_ascii=False)
        if len(body.encode()) > MAX_BYTES:
            raise InvalidEvent("Evento demasiado grande")
        conn = self._connect()
        try:
            conn.send(destination=EVENTS[event_type][0], body=body,
                      headers={"content-type": "application/json; charset=utf-8", "persistent": "true",
                               "event-id": event_id, "correlation-id": correlation_id or ""})
        except Exception as exc:
            raise EventBusUnavailable("No se pudo publicar") from exc
        finally:
            if conn.is_connected():
                conn.disconnect()
        log.info(json.dumps({"event": "published", "type": event_type, "event_id": event_id}))
        return event_id

    def consume(self, event_type: str, handler):
        """Suscribe handler(payload, event_id) a la cola del evento. Ack si termina bien; si lanza InvalidEvent o
        cualquier excepción, nack → el broker lo manda a DLQ.<cola>. Devuelve la conexión (el llamador la mantiene viva)."""
        _validate(event_type, {k: None for k in EVENTS[event_type][1]})
        queue = EVENTS[event_type][0]

        class Listener:
            def __init__(self): self.conn = None
            def on_error(self, frame): log.error(json.dumps({"event": "broker_error"}))
            def on_disconnected(self): log.warning(json.dumps({"event": "disconnected"}))
            def on_message(self, frame):
                ack_id = frame.headers.get("ack") or frame.headers.get("ack-id") or frame.headers.get("message-id")
                try:
                    if len(frame.body.encode()) > MAX_BYTES:
                        raise InvalidEvent("Evento demasiado grande")
                    msg = json.loads(frame.body)
                    if msg.get("type") != event_type or not msg.get("event_id"):
                        raise InvalidEvent("Mensaje inesperado")
                    _validate(event_type, msg.get("payload") or {})
                    handler(msg["payload"], msg["event_id"])
                    self.conn.ack(id=ack_id)
                except Exception as exc:  # no se registra el contenido del mensaje
                    log.error(json.dumps({"event": "rejected", "type": event_type, "error": type(exc).__name__}))
                    self.conn.nack(id=ack_id, requeue="false")

        listener = Listener()
        conn = self._connect(listener)
        listener.conn = conn
        conn.subscribe(destination=queue, id=f"{self.user}-{event_type}", ack="client-individual", headers={"prefetch-count": "1"})
        return conn
