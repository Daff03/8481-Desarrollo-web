import importlib.util, json, pathlib, sys, threading
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("notifier_main", ROOT / "svc-notifier" / "main.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


class Mem:
    def __init__(self): self.sent = []
    def send(self, to, subject, body): self.sent.append((to, subject, body))


def test_verificacion_incluye_enlace_con_token(mod):
    s = Mem(); n = mod.Notifier(s)
    n.handle({"to": "ana@correo.cl", "template": "verificar_correo", "data": {"token": "abc123"}}, "e1")
    to, subject, body = s.sent[0]
    assert to == "ana@correo.cl" and "verificar.php?token=abc123" in body and "Confirma" in subject


def test_boleta_formatea_montos_en_clp(mod):
    s = Mem(); n = mod.Notifier(s)
    n.handle({"to": "a@b.cl", "template": "boleta", "data": {"numero": 7, "nombre": "Ana", "total": 27980,
              "items": [{"cantidad": 2, "nombre": "Kebab Mixto", "subtotal": 27980}]}}, "e2")
    assert "Boleta N° 7" in s.sent[0][1] and "$27.980" in s.sent[0][2] and "2 x Kebab Mixto" in s.sent[0][2]


def test_duplicado_no_reenvia(mod):
    s = Mem(); n = mod.Notifier(s)
    p = {"to": "a@b.cl", "template": "verificar_correo", "data": {"token": "t"}}
    n.handle(p, "e3"); n.handle(p, "e3")
    assert len(s.sent) == 1


@pytest.mark.parametrize("payload", [
    {"to": "no-es-correo", "template": "verificar_correo", "data": {"token": "t"}},
    {"to": "a@b.cl", "template": "desconocida", "data": {}},
    {"to": "a@b.cl", "template": "boleta", "data": {"numero": 1}},
    {"to": "a@b.cl", "template": "verificar_correo", "data": "texto"},
])
def test_mensaje_invalido_lanza_error_para_ir_a_dlq(mod, payload):
    s = Mem()
    with pytest.raises(ValueError):
        mod.Notifier(s).handle(payload, "ex")
    assert s.sent == []


def test_file_sender_escribe_jsonl(mod, tmp_path):
    path = tmp_path / "sub" / "outbox.jsonl"
    mod.FileSender(str(path)).send("a@b.cl", "Hola", "Cuerpo ñ")
    line = json.loads(path.read_text(encoding="utf-8").strip())
    assert line["to"] == "a@b.cl" and line["body"] == "Cuerpo ñ" and "ts" in line


def test_consumidor_reintenta_si_el_broker_cae(mod):
    class Bus:
        calls = 0
        def consume(self, t, h):
            Bus.calls += 1
            if Bus.calls < 3: raise ConnectionError()
            stop.set()
            class C:
                def is_connected(self): return False
            return C()
    stop = threading.Event()
    mod.run_consumer(Bus(), mod.Notifier(Mem()), stop, retry_seconds=0)
    assert Bus.calls == 3
