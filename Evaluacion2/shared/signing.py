"""Firmas HMAC-SHA256: webhooks del proveedor de pagos y fichas de pago firmadas.
Todas las comparaciones son en tiempo constante y aceptan la clave vigente y la anterior (ventana de rotación)."""
import base64, hashlib, hmac, json, time


def sign_bytes(secret: str, data: bytes) -> str:
    return hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()


def verify_bytes(secrets: list, data: bytes, signature: str) -> bool:
    sig = (signature or "").removeprefix("sha256=")
    return any(s and hmac.compare_digest(sign_bytes(s, data), sig) for s in secrets)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def make_token(secret: str, claims: dict, ttl: int) -> str:
    body = _b64(json.dumps({**claims, "exp": int(time.time()) + ttl}, separators=(",", ":")).encode())
    return f"{body}.{sign_bytes(secret, body.encode())}"


def read_token(secrets: list, token: str) -> dict | None:
    """Devuelve las claims si la firma es válida y no venció; si no, None."""
    try:
        body, sig = token.split(".", 1)
        if not verify_bytes(secrets, body.encode(), sig):
            return None
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return claims if claims.get("exp", 0) > time.time() else None
    except Exception:
        return None
