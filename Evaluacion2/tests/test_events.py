import json, pathlib, sys
import xml.etree.ElementTree as ET
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import gen_secrets
from shared.events import EventBus, EventBusUnavailable, InvalidEvent


class FakeProvider:
    def get(self, ref): return {"current": f"valor-{ref}-de-prueba-32-bytes", "previous": None}


class FakeConn:
    def __init__(self, broker): self.broker, self.listener, self.connected, self.acks, self.nacks = broker, None, False, [], []
    def set_listener(self, name, l): self.listener = l
    def connect(self, user, pwd, wait=True):
        if self.broker.down: raise ConnectionRefusedError()
        self.broker.logins.append((user, pwd)); self.connected = True
    def is_connected(self): return self.connected
    def disconnect(self): self.connected = False
    def send(self, destination, body, headers): self.broker.sent.append((destination, body, headers))
    def subscribe(self, destination, id, ack, headers): self.broker.subs.append((destination, ack, headers))
    def ack(self, id): self.acks.append(id)
    def nack(self, id, **kw): self.nacks.append(id)


class Broker:
    def __init__(self): self.down, self.sent, self.logins, self.subs, self.conns = False, [], [], [], []
    def factory(self, host, port):
        c = FakeConn(self); self.conns.append(c); return c


class Frame:
    def __init__(self, body, ack="a1"): self.body, self.headers = body, {"ack": ack}


@pytest.fixture()
def bus():
    b = Broker()
    return EventBus(FakeProvider(), "payments", host="h", port=1, connection_factory=b.factory), b


PAGO = {"order_id": "o1", "amount": 12000, "provider_ref": "sim-1"}


def test_publica_persistente_con_credencial_propia(bus):
    eb, b = bus
    eid = eb.publish("pago.aprobado", PAGO)
    dest, body, headers = b.sent[0]
    assert dest == "/queue/pagos.aprobados" and headers["persistent"] == "true" and headers["event-id"] == eid
    assert json.loads(body)["payload"] == PAGO
    assert b.logins == [("payments", "valor-mq-payments-de-prueba-32-bytes")]
    assert not b.conns[0].connected  # cierra la conexión


def test_reintento_conserva_event_id(bus):
    eb, b = bus
    assert eb.publish("pago.aprobado", PAGO, event_id="e-1") == "e-1" == json.loads(b.sent[0][1])["event_id"]


def test_evento_invalido_no_se_publica(bus):
    eb, b = bus
    with pytest.raises(InvalidEvent): eb.publish("pago.aprobado", {"order_id": "o1"})
    with pytest.raises(InvalidEvent): eb.publish("desconocido", {})
    assert b.sent == []


def test_broker_caido_levanta_error_controlado(bus):
    eb, b = bus
    b.down = True
    with pytest.raises(EventBusUnavailable): eb.publish("pago.aprobado", PAGO)


def test_consumidor_ack_si_el_handler_termina(bus):
    _, b = bus
    eb = EventBus(FakeProvider(), "orders", connection_factory=b.factory)
    recibidos = []
    conn = eb.consume("pago.aprobado", lambda p, eid: recibidos.append((p, eid)))
    assert b.subs[0][0] == "/queue/pagos.aprobados" and b.subs[0][1] == "client-individual"
    conn.listener.on_message(Frame(json.dumps({"event_id": "e1", "type": "pago.aprobado", "payload": PAGO})))
    assert recibidos == [(PAGO, "e1")] and conn.acks == ["a1"] and conn.nacks == []


def test_consumidor_nack_si_el_mensaje_es_invalido_o_el_handler_falla(bus):
    _, b = bus
    eb = EventBus(FakeProvider(), "orders", connection_factory=b.factory)

    def falla(p, eid): raise RuntimeError("boom")
    conn = eb.consume("pago.aprobado", falla)
    for body in ("no es json", json.dumps({"event_id": "e", "type": "otro", "payload": PAGO}),
                 json.dumps({"event_id": "e", "type": "pago.aprobado", "payload": {"order_id": "x"}}),
                 json.dumps({"event_id": "e", "type": "pago.aprobado", "payload": PAGO})):
        conn.listener.on_message(Frame(body))
    assert conn.nacks == ["a1"] * 4 and conn.acks == []


# ---- configuración generada del broker ----
@pytest.fixture()
def xml(tmp_path):
    gen_secrets.generate(out=tmp_path, policy_path=ROOT / "secrets-manager" / "policy.json")
    text = (tmp_path / "activemq" / "activemq.xml").read_text()
    store = json.loads((tmp_path / "manager" / "store.json").read_text())
    return text, ET.fromstring(text), store


def test_activemq_xml_valido_con_un_usuario_por_servicio(xml):
    text, root, store = xml
    ns = {"a": "http://activemq.apache.org/schema/core"}
    users = {u.get("username"): u.get("password") for u in root.iterfind(".//a:authenticationUser", ns)}
    assert set(users) == {"payments", "orders", "clients", "notifier"}
    assert all(users[u] == store[f"mq-{u}"]["current"] for u in users) and len(set(users.values())) == 4
    assert root.find(".//a:simpleAuthenticationPlugin", ns).get("anonymousAccessAllowed") == "false"
    assert "jetty" not in text  # sin consola web


def test_activemq_permisos_por_cola(xml):
    _, root, _ = xml
    ns = {"a": "http://activemq.apache.org/schema/core"}
    e = {x.get("queue"): x for x in root.iterfind(".//a:authorizationEntry", ns) if x.get("queue")}
    assert (e["pagos.aprobados"].get("write"), e["pagos.aprobados"].get("read")) == ("payments", "orders")
    assert e["notificaciones.correo"].get("write") == "clients,orders" and e["notificaciones.correo"].get("read") == "notifier"


def test_cola_con_servicio_sin_referencia_falla(tmp_path):
    q = tmp_path / "q.json"; q.write_text('{"x": {"write": ["fantasma"], "read": ["orders"]}}')
    with pytest.raises(SystemExit):
        gen_secrets.activemq_xml({"mq-orders": {"current": "k"}}, ["mq-orders"], q)
