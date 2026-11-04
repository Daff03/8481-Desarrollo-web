"""Lista blanca de rutas externas. Todo lo que no esté aquí responde 404; un verbo no listado, 405.
access: anon (sin sesión) · optional (identidad si hay sesión) · user (sesión obligatoria).
roles: si se indica, además exige uno de esos roles. El servicio destino vuelve a comprobar propiedad y reglas."""
from dataclasses import dataclass

CLIENTE, CAJERO, ADMIN = "cliente", "cajero", "administrador"
STAFF = frozenset({CAJERO, ADMIN})
ONLY_ADMIN = frozenset({ADMIN})
CUSTOMER_OR_STAFF = frozenset({CLIENTE, CAJERO, ADMIN})


@dataclass(frozen=True)
class Route:
    method: str
    path: str               # ruta externa bajo /api/v1, con {parametros}
    target: str             # auth | clients | inventory | orders | payments | graphql
    dest: str               # ruta interna en el servicio destino
    access: str = "user"
    roles: frozenset | None = None
    query: tuple = ()       # parámetros de consulta admitidos; cualquier otro → 400
    headers: tuple = ()     # únicas cabeceras del navegador/proveedor que se reenvían (p. ej. la firma del webhook)
    sid: str = ""           # id de servicio (trazabilidad con el informe)


R = Route
ROUTES: list[Route] = [
    # --- Autenticación y registro ---
    R("POST", "/auth/register", "clients", "/clients/register", "anon", sid="S03"),
    R("POST", "/auth/verify-email", "auth", "/verify-email", "anon", sid="S04"),
    # /auth/login, /auth/logout y /auth/session los resuelve el propio gateway (cookie), ver main.py

    # --- Catálogo (inventory) ---
    R("GET", "/products", "inventory", "/products", "anon", query=("available", "categoria", "page", "limit"), sid="S01"),
    R("GET", "/products/{id}", "inventory", "/products/{id}", "anon", sid="S02"),
    R("GET", "/promotions", "inventory", "/promotions", "anon", sid="S35"),
    R("POST", "/products", "inventory", "/products", roles=ONLY_ADMIN, sid="S14"),
    R("PUT", "/products/{id}", "inventory", "/products/{id}", roles=ONLY_ADMIN, sid="S15"),
    R("PATCH", "/products/{id}/availability", "inventory", "/products/{id}/availability", roles=STAFF, sid="S16"),
    R("DELETE", "/products/{id}", "inventory", "/products/{id}", roles=ONLY_ADMIN, sid="S17"),
    R("GET", "/admin/products", "inventory", "/admin/products", roles=STAFF, query=("categoria", "page", "limit"), sid="S40"),

    # --- Clientes ---
    R("GET", "/me", "clients", "/clients/me", sid="S07"),
    R("PUT", "/me", "clients", "/clients/me", roles=frozenset({CLIENTE}), sid="S08"),
    R("GET", "/me/addresses", "clients", "/clients/me/addresses", roles=frozenset({CLIENTE}), sid="S36"),
    R("POST", "/me/addresses", "clients", "/clients/me/addresses", roles=frozenset({CLIENTE}), sid="S37"),
    R("PUT", "/me/addresses/{id}", "clients", "/clients/me/addresses/{id}", roles=frozenset({CLIENTE}), sid="S38"),
    R("DELETE", "/me/addresses/{id}", "clients", "/clients/me/addresses/{id}", roles=frozenset({CLIENTE}), sid="S39"),
    R("GET", "/clients", "clients", "/clients", roles=STAFF, query=("page", "limit", "q"), sid="S09"),
    R("GET", "/clients/{id}", "clients", "/clients/{id}", roles=STAFF, sid="S41"),
    R("POST", "/clients", "clients", "/clients", roles=ONLY_ADMIN, sid="S10"),
    R("PUT", "/clients/{id}", "clients", "/clients/{id}", roles=ONLY_ADMIN, sid="S11"),
    R("DELETE", "/clients/{id}", "clients", "/clients/{id}", roles=ONLY_ADMIN, sid="S12"),
    R("GET", "/users", "auth", "/users", roles=ONLY_ADMIN, query=("page", "limit"), sid="S13"),

    # --- Pedidos, reservas, despacho y reportes (orders) ---
    R("POST", "/orders", "orders", "/orders", roles=CUSTOMER_OR_STAFF, sid="S18"),
    R("GET", "/orders", "orders", "/orders", query=("page", "limit", "estado"), sid="S19"),
    R("GET", "/orders/{id}", "orders", "/orders/{id}", sid="S20"),
    R("POST", "/orders/{id}/cancel", "orders", "/orders/{id}/cancel", sid="S21"),
    R("GET", "/orders/{id}/receipt", "orders", "/orders/{id}/receipt", sid="S25"),
    R("GET", "/reports/sales", "orders", "/reports/sales", roles=ONLY_ADMIN, query=("desde", "hasta"), sid="S26"),
    R("GET", "/dispatch", "orders", "/dispatch", roles=STAFF, query=("estado", "page", "limit"), sid="S27"),
    R("PATCH", "/dispatch/{id}", "orders", "/dispatch/{id}", roles=STAFF, sid="S28"),
    R("PATCH", "/orders/{id}/status", "orders", "/orders/{id}/status", roles=STAFF, sid="S29"),
    R("POST", "/reservations", "orders", "/reservations", "optional", sid="S30"),
    R("GET", "/reservations", "orders", "/reservations", roles=STAFF, query=("estado", "page", "limit"), sid="S31"),
    R("PATCH", "/reservations/{id}", "orders", "/reservations/{id}", roles=STAFF, sid="S32"),
    R("GET", "/delivery/coverage", "orders", "/delivery/coverage", "anon", query=("comuna",), sid="S34"),

    # --- Pagos ---
    R("POST", "/payments", "payments", "/payments", roles=CUSTOMER_OR_STAFF, sid="S22"),
    R("GET", "/payments/{id}", "payments", "/payments/{id}", sid="S24"),
    # El proveedor (simulado) no tiene sesión: payments valida la firma HMAC y la idempotencia del evento.
    R("POST", "/webhooks/payments", "payments", "/webhooks/provider", "anon", headers=("x-signature",), sid="S23"),

    # --- Agregaciones ---
    R("POST", "/graphql", "graphql", "/graphql", sid="S33"),
]
