"""Cliente del Secrets Manager con caché corta y fallo cerrado."""
import os, time
import httpx


class SecretUnavailable(Exception):
    """El gestor no responde y la caché venció: el servicio debe fallar cerrado (503)."""


class SecretProvider:
    def __init__(self, base_url=None, service_id=None, service_key=None, ttl=60, timeout=2.0, client=None):
        self.base = (base_url or os.environ["SECRETS_MANAGER_URL"]).rstrip("/")
        self.headers = {"X-Service-Id": service_id or os.environ["SERVICE_ID"],
                        "X-Service-Key": service_key or os.environ["SERVICE_KEY"]}
        self.ttl, self.timeout, self._client = ttl, timeout, client
        self._cache: dict[str, tuple[float, dict]] = {}

    def get(self, ref: str) -> dict:
        """Devuelve {'current': ..., 'previous': ... | None}."""
        hit = self._cache.get(ref)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        try:
            http = self._client or httpx
            r = http.get(f"{self.base}/secrets/{ref}", headers=self.headers, timeout=self.timeout)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise SecretUnavailable(f"No se pudo obtener la referencia '{ref}'") from exc
        data = {"current": r.json()["current"], "previous": r.json()["previous"]}
        self._cache[ref] = (time.monotonic(), data)
        return data
