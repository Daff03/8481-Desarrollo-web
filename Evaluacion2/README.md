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
```
python -m venv <ruta-fuera-del-repo> && <venv>/Scripts/pip install -r requirements-dev.txt
<venv>/Scripts/python -m pytest tests
```
No necesitan MongoDB: `auth` se prueba con `mongomock` y el gateway con servicios simulados.

## Secretos
`python scripts/gen_secrets.py` crea `secrets/` (ignorada por git) con los secretos, las credenciales de cada servicio
y un `.env` por servicio. Las referencias permitidas por servicio están en `secrets-manager/policy.json`.
`.env.example` solo contiene referencias simbólicas.

## Arranque (Docker)
```
python scripts/gen_secrets.py            # una vez; con --force se regeneran y hay que borrar el volumen: docker compose down -v
docker compose up -d --build
docker compose ps                        # todos "healthy"; solo el gateway publica el puerto 8000
docker compose down                      # detener
```
Redes: `public` (solo el gateway) y `private` (`internal: true`, sin salida a Internet; Mongo, secrets-manager y
servicios no publican puertos). MongoDB crea un usuario por servicio con permisos solo sobre su base (`<servicio>_db`).
Los contenedores corren con sistema de archivos de solo lectura, sin capacidades y sin privilegios nuevos.
En Linux, los archivos de `secrets/` (permisos 600) deben ser legibles por el usuario del contenedor.

Cuentas de personal de la demo: `admin@alsahara.cl` y `cajero@alsahara.cl`; sus contraseñas se generan en `secrets/seed.env`
(no están en el repositorio). Los clientes se registran desde `registro.php`.

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
