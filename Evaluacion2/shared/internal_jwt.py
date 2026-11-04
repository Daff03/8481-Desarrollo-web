"""Identidad interna firmada: el gateway la emite (30 s, un solo destino) y cada servicio la verifica.
El navegador nunca la ve ni puede fabricarla: la clave 'internal-jwt' solo la tienen gateway y servicios."""
import time, uuid
import jwt

ISSUER = "gateway"
ISSUERS = ["gateway", "graphql-gateway"]  # el GraphQL Gateway re-emite la identidad del usuario para cada servicio destino
TTL_SECONDS = 30


class InvalidIdentity(Exception):
    pass


def sign(secret: str, sub: str | None, role: str | None, audience: str, correlation_id: str, ttl: int = TTL_SECONDS, issuer: str = ISSUER) -> str:
    now = int(time.time())
    claims = {"iss": issuer, "aud": audience, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex,
              "sub": sub, "role": role, "cid": correlation_id}
    return jwt.encode(claims, secret, algorithm="HS256")


def verify(token: str, secrets: list[str], audience: str) -> dict:
    """Acepta la clave vigente y la anterior (ventana de rotación). Rechaza otro destino, otro emisor y tokens vencidos."""
    for s in filter(None, secrets):
        try:
            return jwt.decode(token, s, algorithms=["HS256"], audience=audience, issuer=ISSUERS,
                              options={"require": ["exp", "iat", "aud", "iss"]})
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as exc:
            raise InvalidIdentity(str(exc)) from exc
    raise InvalidIdentity("firma inválida")
