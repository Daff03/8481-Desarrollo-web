# Al Sahara: backend seguro (Caso 27)
Evaluación Unidad 2, Desarrollo Web (UNAB). Integrantes: Daniel Ferreira, Rachel Mendoza.
Entrega: 9-nov-2026.

## Estructura
| Carpeta | Contenido | Estado |
|---|---|---|
| `frontend/` | PHP + Bootstrap + JS (XAMPP, puerto 8080) | v1 |
| `gateway/` | API Gateway (8000, único público): lista blanca, cookie HttpOnly, roles, CSRF, límites | listo |
| `auth/` | Usuarios, Argon2id, sesiones, bloqueo por intentos (8100, privado) | listo |
| `secrets-manager/` | Secretos por referencia, permisos por servicio, rotación (8200, privado) | listo |
| `shared/` | `secret_provider.py`, `internal_jwt.py` | listo |
| `svc-inventory/` | Catálogo, disponibilidad, stock atómico, promociones, seed de los 12 platos (8400, privado) | listo |
| `svc-clients/` | Registro, perfil, hasta 5 direcciones, mantenedor, baja con anonimización (8300, privado) | listo |
| `svc-orders/` | Pedidos y sus estados, anulación con motivo, cobertura 3 km, boleta, despacho, reservas de mesa, reporte de ventas (8500, privado) | listo |
| `svc-payments/` | Inicio de pago con el monto real, webhook firmado (HMAC) e idempotente, publica `pago.aprobado` (8600, privado) | listo |
| `svc-notifier/` | Consume `notificaciones.correo`; adaptador de pruebas que escribe en `mail-outbox/outbox.jsonl` | listo |
| `provider-sim/` | Proveedor de pagos simulado, fuera de la red privada (9000). Solo pruebas | listo |
| `activemq/` + `shared/events.py` | Eventos entre servicios (STOMP): `pagos.aprobados`, `notificaciones.correo` | listo (sin probar contra broker real) |
| `graphql-gateway/` | Agregaciones `resumenPedido`/`misPedidos` (orders + inventory + payments), `anularPedido`; autorización por campo, límites de profundidad y costo, batching (8700, privado) | listo |

## Pruebas
Requieren **Python 3.12** (la versión de las imágenes) y no necesitan Docker ni MongoDB: los servicios vecinos, ActiveMQ y Mongo se simulan (`mongomock`).
```
python -m venv C:\dev\alsahara-venv                       # fuera del repositorio
C:\dev\alsahara-venv\Scripts\pip install -r requirements-dev.txt
C:\dev\alsahara-venv\Scripts\python -m pytest tests     # 176 pruebas
```
`tests/test_consistencia.py` vigila que versiones, puertos, referencias de secretos, compose, Dockerfiles y llamadas del frontend sigan cuadrando.

## Levantar el sistema con Docker
**Guía completa paso a paso (equipo nuevo, con todas las instalaciones): [docs/GUIA_LEVANTAR_DOCKER.md](docs/GUIA_LEVANTAR_DOCKER.md).** Resumen:
```
copy .env.example .env                    # y ajusta FRONTEND_URL a la URL real de tu frontend
python scripts/gen_secrets.py             # una vez (o con Docker, ver la guía); crea ./secrets (ignorada por git)
docker compose up -d --build              # primera vez: 5 a 15 minutos
docker compose ps                         # los 12 servicios en "healthy"
docker compose down                       # detener (docker compose down -v borra los datos)
```
- Solo se publican dos puertos: el gateway (`8000`) y el proveedor de pagos simulado (`9000`). Todo lo demás vive en la red `private` (`internal: true`, sin salida a Internet).
- `gen_secrets.py` crea los secretos, las credenciales de cada servicio, el usuario de Mongo y de ActiveMQ de cada servicio y las contraseñas de las cuentas de la demo. Si lo regeneras con `--force`, borra antes los datos (`docker compose down -v`).
- Cuentas de personal: `admin@alsahara.cl` y `cajero@alsahara.cl`; sus contraseñas están en `secrets/seed.env` (no están en el repositorio). Los clientes se registran desde `registro.php`; el enlace de verificación llega a `mail-outbox/outbox.jsonl`.
- Los contenedores corren con sistema de archivos de solo lectura, sin capacidades y sin privilegios nuevos. MongoDB crea un usuario por servicio con permisos solo sobre su base (`<servicio>_db`).
- Las referencias de secretos permitidas por servicio están en `secrets-manager/policy.json`; `.env.example` no contiene secretos.

## Versiones verificadas
| Pieza | Versión |
|---|---|
| Python (pruebas e imágenes) | 3.12.16 (`python:3.12.16-slim`) |
| Paquetes | fijados en cada `requirements.txt` (fastapi 0.162.0, pydantic 2.14.2, pymongo 4.19.0, PyJWT 2.15.1, argon2-cffi 25.1.0, stomp.py 9.0.0, graphql-core 3.3.1…) |
| MongoDB | `mongo:7.0.45` |
| ActiveMQ Classic | `apache/activemq-classic:6.1.8` |
| Docker Desktop / Engine / Compose | 4.98.0 / 29.9.2 / v5.6.1 |
| XAMPP (frontend) | PHP 8.2.x (probado 8.2.12) |

## Flujo de compra (verificable con las pruebas)
1. `pedido.php` → `POST /orders` (solo slugs y cantidades): `orders` reserva stock en `inventory` y calcula precios; estado CREADO.
2. `pago.php` → `POST /payments`: `payments` pide a `orders` el monto real y devuelve la URL de la pasarela firmada.
3. En la pasarela (`provider-sim`, puerto 9000) se aprueba o rechaza; el proveedor avisa al backend con un webhook firmado.
4. `payments` valida firma, ventana de 5 min, monto e idempotencia, y publica `pago.aprobado` en ActiveMQ.
5. `orders` consume el evento (idempotente por `event_id`), pasa a PAGADO, emite la boleta y encola el correo.
6. Un pedido sin pagar en 30 min se anula solo y devuelve el stock.

## Flujo de una solicitud
navegador → gateway (valida Origin, ruta, verbo, cookie → `auth /session/verify`, rol) → servicio privado con
`X-Caller-Key` (credencial `gw-*`) e `X-Internal-Identity` (JWT de 30 s para ese destino). Los servicios deben
verificar ambas cosas con `shared/internal_jwt.py` y comprobar propiedad del recurso.
