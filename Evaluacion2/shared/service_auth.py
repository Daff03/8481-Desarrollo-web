"""Guardia común de los servicios privados. Un servicio acepta solo llamadas con:
  1. credencial del llamador (X-Caller + X-Caller-Key, comparada con la referencia simbólica de ese tramo), y
  2. si viene del gateway y la ruta lo exige, identidad interna firmada (X-Internal-Identity) emitida para este servicio.
El navegador no llega aquí: la red privada no tiene puertos publicados. Esto protege además ante un gateway mal configurado."""
import secrets
from typing import NamedTuple

from fastapi import Depends, Header, HTTPException

from shared import internal_jwt


class Principal(NamedTuple):
    caller: str            # "gateway" u otro servicio
    user_id: str | None    # solo si hay identidad de usuario
    role: str | None


def make_guard(audience: str, caller_refs: dict[str, str], get_provider):
    """audience: nombre de este servicio en el JWT. caller_refs: llamador → referencia de su credencial."""

    def guard(*, roles: frozenset | set | None = None, services: tuple = (), gateway: bool = True, delegates: tuple = ()):
        """roles: exige identidad de usuario con uno de esos roles. services: servicios internos permitidos (sin usuario).
        gateway=False: la ruta es solo interna. delegates: otros llamadores (p. ej. graphql-gateway) que actúan con la identidad de un usuario."""
        def dep(x_caller: str | None = Header(default=None), x_caller_key: str | None = Header(default=None),
                x_internal_identity: str | None = Header(default=None), provider=Depends(get_provider)) -> Principal:
            ref = caller_refs.get(x_caller or "")
            if not ref or not x_caller_key:
                raise HTTPException(status_code=401, detail="Credencial de servicio no válida")
            try:
                s = provider.get(ref)
            except Exception:  # gestor de secretos caído: falla cerrado
                raise HTTPException(status_code=503, detail="Servicio no disponible")
            if not any(v and secrets.compare_digest(v, x_caller_key) for v in (s["current"], s["previous"])):
                raise HTTPException(status_code=401, detail="Credencial de servicio no válida")

            if x_caller in services:
                return Principal(x_caller, None, None)
            if not ((x_caller == "gateway" and gateway) or x_caller in delegates):
                raise HTTPException(status_code=403, detail="Llamador no permitido en esta ruta")

            user_id = role = None
            if x_internal_identity or roles:
                if not x_internal_identity:
                    raise HTTPException(status_code=401, detail="Identidad requerida")
                try:
                    jwt_keys = provider.get("internal-jwt")
                    claims = internal_jwt.verify(x_internal_identity, [jwt_keys["current"], jwt_keys["previous"]], audience)
                except internal_jwt.InvalidIdentity:
                    raise HTTPException(status_code=401, detail="Identidad no válida")
                except Exception:
                    raise HTTPException(status_code=503, detail="Servicio no disponible")
                user_id, role = claims.get("sub"), claims.get("role")
            if roles and role not in roles:
                raise HTTPException(status_code=403, detail="Sin permiso")
            return Principal(x_caller, user_id, role)
        return dep
    return guard
