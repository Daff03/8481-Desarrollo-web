"""Secrets Manager: entrega secretos por referencia simbólica a consumidores autenticados.
Nunca registra ni devuelve valores en logs. Puerto interno 8200 (sin publicar)."""
import hashlib, json, logging, os, pathlib, secrets, threading, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException

SECRETS_DIR = pathlib.Path(os.environ.get("SECRETS_DIR", "secrets"))
POLICY_PATH = pathlib.Path(os.environ.get("POLICY_PATH", pathlib.Path(__file__).with_name("policy.json")))
GRACE_SECONDS = int(os.environ.get("ROTATION_GRACE_SECONDS", "300"))
DUMMY_HASH = hashlib.sha256(b"dummy").hexdigest()

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("secrets-manager")
STATE: dict = {}
LOCK = threading.Lock()


def audit(consumer, ref, result):
    # Auditoría: quién, qué referencia, cuándo y resultado. Jamás el valor.
    log.info(json.dumps({"ts": int(time.time()), "consumer": consumer, "ref": ref, "result": result}))


def load_state():
    STATE["store"] = json.loads((SECRETS_DIR / "store.json").read_text())
    STATE["hashes"] = json.loads((SECRETS_DIR / "service_key_hashes.json").read_text())
    STATE["policy"] = json.loads(POLICY_PATH.read_text())


@asynccontextmanager
async def lifespan(app):
    load_state()
    yield


app = FastAPI(title="secrets-manager", lifespan=lifespan, docs_url=None, redoc_url=None)


def authenticate(service_id: str | None, key: str | None) -> str:
    expected = STATE["hashes"].get(service_id or "")
    presented = hashlib.sha256((key or "").encode()).hexdigest()
    ok = secrets.compare_digest(expected or DUMMY_HASH, presented) and expected is not None
    if not ok:
        audit(service_id, None, "auth_failed")
        raise HTTPException(status_code=401, detail="Credencial de servicio no válida")
    return service_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/secrets/{ref}")
def get_secret(ref: str, x_service_id: str = Header(default=None), x_service_key: str = Header(default=None)):
    consumer = authenticate(x_service_id, x_service_key)
    allowed = STATE["policy"]["refs"].get(ref, [])
    if consumer not in allowed:  # mismo 403 si la referencia no existe: no revela qué hay
        audit(consumer, ref, "denied")
        raise HTTPException(status_code=403, detail="Sin permiso para esa referencia")
    entry = STATE["store"].get(ref)
    if entry is None:  # está en la política pero no se generó: regenerar con gen_secrets.py --force
        audit(consumer, ref, "missing_in_store")
        raise HTTPException(status_code=503, detail="Secreto no disponible")
    previous = entry["previous"] if time.time() - entry["rotated_at"] < GRACE_SECONDS else None
    audit(consumer, ref, "ok")
    return {"ref": ref, "current": entry["current"], "previous": previous}


@app.post("/admin/rotate/{ref}")
def rotate(ref: str, x_service_id: str = Header(default=None), x_service_key: str = Header(default=None)):
    consumer = authenticate(x_service_id, x_service_key)
    if consumer not in STATE["policy"]["rotators"]:
        audit(consumer, ref, "denied")
        raise HTTPException(status_code=403, detail="Sin permiso para rotar")
    with LOCK:
        entry = STATE["store"].get(ref)
        if entry is None:
            raise HTTPException(status_code=404, detail="Referencia desconocida")
        entry.update(previous=entry["current"], current=secrets.token_urlsafe(32), rotated_at=time.time())
        tmp = SECRETS_DIR / "store.json.tmp"
        tmp.write_text(json.dumps(STATE["store"], indent=2))
        tmp.replace(SECRETS_DIR / "store.json")
    audit(consumer, ref, "rotated")
    return {"ref": ref, "rotated": True, "grace_seconds": GRACE_SECONDS}
