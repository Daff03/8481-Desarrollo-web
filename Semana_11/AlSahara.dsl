workspace "Al Sahara" "Arquitectura Backend Seguro C4 - Restaurante Al Sahara (Caso 27, Evaluación Unidad 2 - Desarrollo Web UNAB)" {

    !identifiers hierarchical

    model {
        // =====================================================
        // ACTORES (Módulo 4 - stakeholders con cuenta o interacción directa)
        // =====================================================
        visitante = person "Visitante" "Persona anónima que consulta la carta y la cobertura de delivery, se registra y solicita una reserva de mesa."
        cliente = person "Cliente" "Cliente registrado (rol cliente) que compra, paga, anula y sigue sus propios pedidos."
        cajero = person "Cajero" "Personal de caja (rol cajero): venta en el local, cocina, despacho, reservas y disponibilidad de platos."
        administrador = person "Administrador" "Rol administrador: todo lo del cajero más mantenedores (productos, clientes, usuarios) y reporte de ventas para el dueño."
        operador = person "Operador del sistema" "Instala y rota secretos con la identidad técnica admin-cli; no accede a datos de negocio."

        // =====================================================
        // SISTEMAS EXTERNOS
        // =====================================================
        pasarela = softwareSystem "Pasarela de pago (provider-sim)" "Proveedor de pagos externo y simulado: el cliente aprueba o rechaza el pago y la pasarela avisa con un webhook firmado HMAC." {
            tags "SistemaExterno"
        }

        // =====================================================
        // SISTEMA EVALUADO
        // =====================================================
        sistema = softwareSystem "Al Sahara - Backend Seguro" "Plataforma de ventas y delivery del restaurante: catálogo, registro y autenticación, pedidos, pagos, boletas, despacho, reservas de mesa y reporte de ventas." {
            tags "SistemaEvaluado"

            frontend = container "Frontend" "Sitio del restaurante: carta, registro, login, carrito, pago, Mi cuenta y reserva de mesa. Ejecuta fetch con credentials: include hacia el gateway." "PHP + Bootstrap 5 + JavaScript (XAMPP, puerto 8080)" {
                tags "Frontend"
            }

            // ---------- API Gateway (Módulo 5) ----------
            apiGateway = container "API Gateway" "Única puerta pública: lista blanca de rutas, Origin, límite de solicitudes, sesión por cookie, rol, JWT interno de 30 s y errores genéricos con correlation_id." "FastAPI / Python 3.12 (puerto 8000, redes public + private)" {
                tags "Gateway"

                httpEntry = component "Adaptador HTTP" "Recibe la solicitud, limita cuerpo (1 MB) y tipo (application/json) y descarta cualquier cabecera de identidad enviada por el navegador." "Módulo de entrada (gateway/main.py)" {
                    tags "EntradaC3"
                }
                routeTable = component "Tabla de rutas (RouteDefinition)" "Lista blanca de 41 rutas S01-S41: verbo, ruta, acceso (anon/optional/user/rol), query permitida y destino. Lo no publicado responde 404 o 405." "Configuración (gateway/routes.py)" {
                    tags "ControlC3"
                }
                originPolicy = component "Política de Origen" "Defensa CSRF: exige Origin permitido en POST, PUT, PATCH y DELETE (el webhook está exento)." "Política (guard)" {
                    tags "ControlC3"
                }
                rateLimiter = component "Limitador de solicitudes" "300 solicitudes por minuto por IP y ruta; 10 logins por minuto. Responde 429 con Retry-After. Hoy en memoria." "Política (RateLimiter)" {
                    tags "ControlC3"
                }
                authnPolicy = component "Política de autenticación" "Verifica la cookie de sesión contra Auth Service y produce el Principal (usuario y rol); 401 si no es válida." "Política (guard)" {
                    tags "ControlC3"
                }
                authzPolicy = component "Política de autorización" "Compara el rol del Principal con los roles de la ruta (Tabla de permisos); 403 si no alcanza." "Política (guard)" {
                    tags "ControlC3"
                }
                sessionHandler = component "Gestor de sesión (cookie)" "Atiende login y logout: emite la cookie HttpOnly / SameSite=Lax (8 h) y la borra al salir. El token nunca viaja en el cuerpo." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                identityIssuer = component "Emisor de identidad interna" "Firma el JWT HS256 de 30 s con claim aud para un único destino." "shared/internal_jwt.py" {
                    tags "IntegracionC3"
                }
                secretProvider = component "Proveedor de secretos" "Obtiene por referencia la credencial gw-* de cada tramo y la clave internal-jwt; caché de 60 s; falla cerrada con 503." "shared/secret_provider.py" {
                    tags "IntegracionC3"
                }
                routeDispatcher = component "Despachador de rutas (ServiceTarget)" "Reenvía al servicio privado con X-Caller-Key e X-Internal-Identity, con plazo de 5 s." "Proxy" {
                    tags "AplicacionC3"
                }
                errorMapper = component "Traductor de errores" "Convierte fallos en respuestas {detail, correlation_id} sin datos internos (401, 403, 404, 405, 413, 415, 422, 429, 503, 504)." "Módulo de errores" {
                    tags "ErrorC3"
                }
            }

            // ---------- Auth Service ----------
            authService = container "Auth Service" "Cuentas, contraseñas, sesiones, roles y bloqueo por intentos fallidos." "FastAPI / Python 3.12 (puerto 8100, red private)" {
                tags "Seguridad"

                authApi = component "API de identidad" "Verifica llamador (X-Caller-Key) e identidad (JWT) y atiende login, logout, /session/verify, /users y verificación de correo." "API interna (ServiceGuard)" {
                    tags "EntradaC3"
                }
                credentialsVerifier = component "Verificador de credenciales" "Compara la contraseña con el hash Argon2id con sal; bloqueo de 15 min tras varios intentos fallidos; 401 idéntico si el correo no existe." "Módulo de seguridad" {
                    tags "ControlC3"
                }
                sessionManager = component "Gestor de sesiones" "Crea tokens opacos, guarda solo su hash SHA-256, TTL de 8 h, revoca al cerrar sesión." "Servicio de identidad" {
                    tags "AplicacionC3"
                }
                verificationTokens = component "Tokens de verificación de correo" "Token de un solo uso con TTL de 24 h, guardado como hash y borrado al verificar." "Servicio de identidad" {
                    tags "AplicacionC3"
                }
                userManager = component "Gestor de usuarios" "Crea y borra cuentas para clients (POST /users) y lista usuarios sin hashes para el administrador (S13)." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                authRepo = component "Repositorio de identidades" "Persiste usuarios, sesiones e intentos de login en auth_db." "Acceso a datos" {
                    tags "PersistenciaC3"
                }
                secretProvider = component "Cliente de secretos" "Lee gw-auth, auth-clients, internal-jwt y db-auth desde el gestor de secretos." "shared/secret_provider.py" {
                    tags "IntegracionC3"
                }
            }

            secretsManager = container "Secrets Manager" "Entrega 24 referencias simbólicas según policy.json; solo admin-cli rota (la clave anterior se acepta 5 min); registra cada lectura en auditoría." "FastAPI / Python 3.12 (puerto 8200, red private)" {
                tags "Seguridad"
            }

            clientsService = container "clients" "Autoridad de los datos personales: registro, perfil, direcciones (máx. 5), mantenedor y baja con anonimización. RUN enmascarado para el personal." "FastAPI / Python 3.12 (puerto 8300, red private)" {
                tags "Privado"
            }

            inventoryService = container "inventory" "Autoridad de catálogo, disponibilidad, stock y promociones. Reserva y libera stock de forma atómica." "FastAPI / Python 3.12 (puerto 8400, red private)" {
                tags "Privado"
            }

            // ---------- orders ----------
            ordersService = container "orders" "Autoridad del estado del pedido: precios y total en el servidor, boleta correlativa, despacho, reservas de mesa, reporte de ventas y anulación automática a los 30 min." "FastAPI / Python 3.12 (puerto 8500, red private)" {
                tags "Privado"

                ordersApi = component "API de pedidos" "ServiceGuard: exige X-Caller-Key del tramo, JWT interno (aud y vigencia) y rol en cada ruta." "API interna" {
                    tags "EntradaC3"
                }
                accessPolicy = component "Política de acceso" "Propiedad por user_id del JWT: un pedido ajeno responde 404, igual que uno inexistente; roles para despacho, reservas y reporte." "Regla de autorización" {
                    tags "ControlC3"
                }
                orderWorkflow = component "Flujo de pedidos" "Calcula precios y total (con promociones), aplica transiciones de estado de forma atómica y la anulación con motivo (CANCEL_FROM por rol y estado)." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                paymentEventConsumer = component "Consumidor de pago.aprobado" "Consume el evento de ActiveMQ de forma idempotente por event_id y pasa el pedido a PAGADO." "Adaptador de mensajería" {
                    tags "IntegracionC3"
                }
                receiptIssuer = component "Emisor de boleta" "Emite la boleta con número correlativo solo cuando el pedido pasa a PAGADO." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                dispatchModule = component "Módulo de despacho" "Cola de despacho y salida del pedido DELIVERY en estado LISTO; conductor obligatorio para EN_CAMINO (S27-S28)." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                reservationsModule = component "Módulo de reservas" "Reserva de mesa anónima o con sesión; el personal confirma o rechaza (S30-S32)." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                salesReport = component "Reporte de ventas" "Consulta agregada solo de pedidos pagados, máx. 366 días, sin datos personales (S26)." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                expirationJob = component "Anulación por vencimiento" "Anula un pedido CREADO sin pagar en 30 min y devuelve el stock." "Tarea programada" {
                    tags "AplicacionC3"
                }
                inventoryAdapter = component "Adaptador de inventario" "POST /internal/reserve y /internal/release (credencial orders-inventory)." "Adaptador privado" {
                    tags "IntegracionC3"
                }
                clientsAdapter = component "Adaptador de clients" "Obtiene los datos del cliente al crear un pedido (/internal/clients/*, credencial orders-clients)." "Adaptador privado" {
                    tags "IntegracionC3"
                }
                outboxPublisher = component "Publicador de correos (outbox)" "Encola notificaciones.correo (boleta y reservas); si ActiveMQ no responde, el outbox reintenta." "Adaptador de mensajería" {
                    tags "IntegracionC3"
                }
                ordersRepo = component "Repositorio de pedidos" "Persiste pedidos, boletas, despachos, reservas y outbox en orders_db." "Acceso a datos" {
                    tags "PersistenciaC3"
                }
            }

            // ---------- payments ----------
            paymentsService = container "payments" "Inicio del pago con el monto real de orders, verificación del webhook firmado y estado del pago." "FastAPI / Python 3.12 (puerto 8600, red private)" {
                tags "Privado"

                paymentsApi = component "API de pagos" "ServiceGuard por tramo; recibe S22, S24 y el webhook S23 (/webhooks/provider)." "API interna" {
                    tags "EntradaC3"
                }
                checkoutBuilder = component "Constructor de pago" "Crea el pago PENDIENTE con el monto pedido a orders y devuelve la URL de la pasarela con ficha firmada HMAC con vencimiento." "Servicio de aplicación" {
                    tags "AplicacionC3"
                }
                webhookVerifier = component "Verificador de webhook" "Valida la firma X-Signature (HMAC-SHA256), la ventana de 5 min y que amount coincida con el monto real; si no, 401." "Módulo de seguridad" {
                    tags "ControlC3"
                }
                idempotency = component "Control de idempotencia" "Registra cada aviso una sola vez por event_id; un repetido responde 200 {duplicate: true} sin efecto." "Regla de negocio" {
                    tags "ControlC3"
                }
                eventPublisher = component "Publicador de pago.aprobado (outbox)" "Publica pago.aprobado en ActiveMQ con outbox y reintentos." "Adaptador de mensajería" {
                    tags "IntegracionC3"
                }
                ordersClient = component "Cliente de orders" "GET /internal/orders/{id} para obtener el monto real (credencial orders-payments)." "Adaptador privado" {
                    tags "IntegracionC3"
                }
                secretProvider = component "Cliente de secretos" "Lee prov-webhook, orders-payments, mq-payments y db-payments." "shared/secret_provider.py" {
                    tags "IntegracionC3"
                }
                paymentsRepo = component "Repositorio de pagos" "Persiste pagos y eventos del webhook en payments_db." "Acceso a datos" {
                    tags "PersistenciaC3"
                }
            }

            // ---------- GraphQL Gateway (Módulo 8) ----------
            graphqlGateway = container "GraphQL Gateway" "Agregaciones privadas de solo composición (sin base de datos): resumenPedido, misPedidos y anularPedido sobre orders, inventory y payments." "FastAPI / Python 3.12 + graphql-core (puerto 8700, red private)" {
                tags "Gateway"

                graphqlEndpoint = component "Endpoint GraphQL" "Recibe POST /graphql desde el API Gateway (S33) con el JWT interno del usuario." "Adaptador GraphQL" {
                    tags "EntradaC3"
                }
                queryLimits = component "Límites de consulta" "Profundidad 6, costo 1000, 5 campos raíz, consulta de máx. 5000 caracteres, plazo 8 s e introspección deshabilitada." "Validación GraphQL (limits.py)" {
                    tags "ControlC3"
                }
                fieldAccess = component "Autorización por campo" "staff_only: cliente y requiereReembolso devuelven null + FORBIDDEN para el rol cliente." "Módulo de autorización" {
                    tags "ControlC3"
                }
                resolvers = component "Resolvers" "resolve_resumen, resolve_mis_pedidos, resolve_anular, resolve_producto y resolve_pago." "Resolvers GraphQL" {
                    tags "AplicacionC3"
                }
                batchLoaders = component "Cargadores por lote (BatchLoader)" "Agrupa las llamadas de productos (hasta 20) y de pagos para evitar el patrón 1+N." "Batching" {
                    tags "AplicacionC3"
                }
                upstreamClient = component "Cliente de subsistemas" "Llama a orders, inventory y payments con la credencial gql-* y re-emite la identidad (JWT de 30 s); plazo de 3 s por llamada." "Adaptador de integración" {
                    tags "IntegracionC3"
                }
                responseComposer = component "Compositor de respuestas" "Entrega errores parciales (producto o pago en null) sin ocultar el fallo; UPSTREAM_UNAVAILABLE si orders no responde." "Módulo de resultados" {
                    tags "ErrorC3"
                }
            }

            // ---------- Mensajería y correo ----------
            notifierService = container "notifier" "Consume notificaciones.correo y escribe el correo (boleta, verificación, reservas); un mensaje inválido va a la DLQ." "FastAPI / Python 3.12 (puerto 8800, red private)" {
                tags "Privado"
            }

            activemq = container "ActiveMQ" "Mensajería asíncrona: pago.aprobado y notificaciones.correo, un usuario por servicio y permisos por cola." "Apache ActiveMQ Classic 6.1.8 (STOMP, puerto 61613)" {
                tags "Broker"
            }

            mailOutbox = container "mail-outbox" "Adaptador de archivo que reemplaza al proveedor de correo: cada correo se escribe como una línea JSON." "Archivo outbox.jsonl" {
                tags "Archivo"
            }

            // ---------- Bases de datos (una por servicio) ----------
            dbAuth = container "auth_db" "Usuarios, hash Argon2id, sesiones (hash SHA-256) e intentos de login." "MongoDB 7 (usuario db-auth)" {
                tags "BaseDatos"
            }
            dbClients = container "clients_db" "Perfiles de clientes y direcciones (RUN con índice único)." "MongoDB 7 (usuario db-clients)" {
                tags "BaseDatos"
            }
            dbInventory = container "inventory_db" "12 platos, precios, stock, promociones y reservas de stock." "MongoDB 7 (usuario db-inventory)" {
                tags "BaseDatos"
            }
            dbOrders = container "orders_db" "Pedidos con detalle embebido, boletas, despachos, reservas de mesa y outbox." "MongoDB 7 (usuario db-orders)" {
                tags "BaseDatos"
            }
            dbPayments = container "payments_db" "Pagos y eventos del webhook (event_id único)." "MongoDB 7 (usuario db-payments)" {
                tags "BaseDatos"
            }
        }

        // =====================================================
        // RELACIONES DE CONTEXTO (C1)
        // =====================================================
        visitante -> sistema "Consulta la carta, se registra y reserva mesa"
        cliente -> sistema "Compra, paga, anula y sigue sus pedidos"
        cajero -> sistema "Vende en el local, gestiona cocina, despacho y reservas"
        administrador -> sistema "Administra catálogo, clientes y usuarios; consulta ventas"
        operador -> sistema "Instala y rota secretos"
        sistema -> pasarela "Entrega la URL de pago con ficha firmada" "HTTPS"
        pasarela -> sistema "Avisa el resultado de cada pago (webhook HMAC)" "HTTPS/JSON"
        cliente -> pasarela "Aprueba o rechaza el pago" "Web"

        // =====================================================
        // RELACIONES DE CONTENEDORES (C2)
        // =====================================================
        visitante -> sistema.frontend "Navega la carta, se registra, inicia sesión y reserva" "Navegador web"
        cliente -> sistema.frontend "Arma el carrito, paga y gestiona Mi cuenta" "Navegador web"
        cajero -> sistema.frontend "Usa los paneles de cocina, caja, despacho y reservas" "Navegador web"
        administrador -> sistema.frontend "Usa los mantenedores y el reporte de ventas" "Navegador web"
        operador -> sistema.secretsManager "Rota secretos con admin-cli" "Script de administración"

        sistema.frontend -> sistema.apiGateway "Solicitudes /api/v1/* con cookie de sesión HttpOnly" "HTTP/JSON"
        sistema.frontend -> pasarela "Redirige al navegador a la pasarela (checkoutUrl)" "HTTP"
        pasarela -> sistema.apiGateway "POST /webhooks/payments con X-Signature (HMAC-SHA256)" "HTTP/JSON"

        sistema.apiGateway -> sistema.authService "Login, logout y verificación de sesión (/session/verify)" "HTTP/JSON (gw-auth)"
        sistema.apiGateway -> sistema.clientsService "Registro, perfil, direcciones y mantenedor de clientes" "HTTP/JSON (gw-clients)"
        sistema.apiGateway -> sistema.inventoryService "Catálogo, disponibilidad y promociones" "HTTP/JSON (gw-inventory)"
        sistema.apiGateway -> sistema.ordersService "Pedidos, boleta, despacho, reservas y reporte" "HTTP/JSON (gw-orders)"
        sistema.apiGateway -> sistema.paymentsService "Inicio de pago, consulta y webhook" "HTTP/JSON (gw-payments)"
        sistema.apiGateway -> sistema.graphqlGateway "POST /graphql (S33)" "HTTP/GraphQL (gw-graphql)"

        sistema.clientsService -> sistema.authService "Crea y borra la cuenta al registrar o dar de baja (POST /users)" "HTTP/JSON (auth-clients)"
        sistema.clientsService -> sistema.activemq "Publica el correo de verificación (notificaciones.correo)" "STOMP (mq-clients)"
        sistema.ordersService -> sistema.clientsService "Obtiene los datos del cliente al crear un pedido" "HTTP/JSON (orders-clients)"
        sistema.ordersService -> sistema.inventoryService "Reserva y libera stock (/internal/reserve, /internal/release)" "HTTP/JSON (orders-inventory)"
        sistema.paymentsService -> sistema.ordersService "Consulta el monto real del pedido (/internal/orders/{id})" "HTTP/JSON (orders-payments)"
        sistema.paymentsService -> sistema.activemq "Publica pago.aprobado" "STOMP (mq-payments)"
        sistema.activemq -> sistema.ordersService "Entrega pago.aprobado" "STOMP (mq-orders)"
        sistema.ordersService -> sistema.activemq "Publica notificaciones.correo (boleta y reservas)" "STOMP (mq-orders)"
        sistema.activemq -> sistema.notifierService "Entrega notificaciones.correo" "STOMP (mq-notifier)"
        sistema.notifierService -> sistema.mailOutbox "Escribe el correo en outbox.jsonl" "Archivo"

        sistema.graphqlGateway -> sistema.ordersService "Lee y anula pedidos" "HTTP/JSON (gql-orders)"
        sistema.graphqlGateway -> sistema.inventoryService "Lee productos por lote" "HTTP/JSON (gql-inventory)"
        sistema.graphqlGateway -> sistema.paymentsService "Lee pagos por lote" "HTTP/JSON (gql-payments)"

        sistema.authService -> sistema.dbAuth "Lee y escribe usuarios y sesiones" "MongoDB"
        sistema.clientsService -> sistema.dbClients "Lee y escribe perfiles y direcciones" "MongoDB"
        sistema.inventoryService -> sistema.dbInventory "Lee y escribe catálogo, stock y reservas" "MongoDB"
        sistema.ordersService -> sistema.dbOrders "Lee y escribe pedidos, boletas, reservas y outbox" "MongoDB"
        sistema.paymentsService -> sistema.dbPayments "Lee y escribe pagos y eventos del webhook" "MongoDB"

        sistema.apiGateway -> sistema.secretsManager "Lee gw-*, gql-* e internal-jwt" "HTTP (clave de servicio)"
        sistema.graphqlGateway -> sistema.secretsManager "Lee gql-* e internal-jwt" "HTTP (clave de servicio)"
        sistema.authService -> sistema.secretsManager "Lee gw-auth, auth-clients, internal-jwt y db-auth" "HTTP (clave de servicio)"
        sistema.clientsService -> sistema.secretsManager "Lee auth-clients, orders-clients, mq-clients y db-clients" "HTTP (clave de servicio)"
        sistema.inventoryService -> sistema.secretsManager "Lee orders-inventory y db-inventory" "HTTP (clave de servicio)"
        sistema.ordersService -> sistema.secretsManager "Lee orders-*, mq-orders y db-orders" "HTTP (clave de servicio)"
        sistema.paymentsService -> sistema.secretsManager "Lee prov-webhook, mq-payments y db-payments" "HTTP (clave de servicio)"
        sistema.notifierService -> sistema.secretsManager "Lee mq-notifier" "HTTP (clave de servicio)"

        // =====================================================
        // COMPONENTES C3 - API GATEWAY
        // =====================================================
        sistema.frontend -> sistema.apiGateway.httpEntry "Envía la solicitud con cookie" "HTTP/JSON"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.routeTable "Busca verbo y ruta en la lista blanca"
        sistema.apiGateway.routeTable -> sistema.apiGateway.originPolicy "Ruta publicada: comprueba Origin"
        sistema.apiGateway.originPolicy -> sistema.apiGateway.rateLimiter "Origin permitido: aplica el límite"
        sistema.apiGateway.rateLimiter -> sistema.apiGateway.authnPolicy "Dentro de la cuota: verifica la sesión"
        sistema.apiGateway.authnPolicy -> sistema.authService "GET /session/verify con la cookie" "HTTP/JSON"
        sistema.apiGateway.authnPolicy -> sistema.apiGateway.authzPolicy "Entrega el Principal (usuario y rol)"
        sistema.apiGateway.authzPolicy -> sistema.apiGateway.routeDispatcher "Rol suficiente: despacha"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.sessionHandler "Rutas de login y logout"
        sistema.apiGateway.sessionHandler -> sistema.authService "POST /login y /logout" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.identityIssuer "Pide JWT de 30 s para el destino"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.secretProvider "Pide la credencial gw-* del tramo"
        sistema.apiGateway.identityIssuer -> sistema.apiGateway.secretProvider "Pide la clave internal-jwt"
        sistema.apiGateway.secretProvider -> sistema.secretsManager "Lee secretos por referencia (caché 60 s)" "HTTP (clave de servicio)"
        sistema.apiGateway.routeDispatcher -> sistema.clientsService "Enruta clientes" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.inventoryService "Enruta catálogo" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.ordersService "Enruta pedidos, despacho, reservas y reporte" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.paymentsService "Enruta pagos y webhook" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway "Enruta consultas GraphQL" "HTTP/GraphQL"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.errorMapper "Reporta timeouts y servicios caídos"
        pasarela -> sistema.apiGateway.httpEntry "Entrega el webhook firmado (exento de Origin y sesión)" "HTTP/JSON"

        // =====================================================
        // COMPONENTES C3 - AUTH SERVICE
        // =====================================================
        sistema.apiGateway -> sistema.authService.authApi "Verifica sesión, login y logout" "HTTP/JSON"
        sistema.clientsService -> sistema.authService.authApi "POST /users y baja de cuenta" "HTTP/JSON"
        sistema.authService.authApi -> sistema.authService.credentialsVerifier "Valida credenciales en el login"
        sistema.authService.authApi -> sistema.authService.sessionManager "Crea, verifica o revoca la sesión"
        sistema.authService.authApi -> sistema.authService.verificationTokens "Verifica el token del correo"
        sistema.authService.authApi -> sistema.authService.userManager "Crea, borra y lista usuarios"
        sistema.authService.credentialsVerifier -> sistema.authService.authRepo "Busca usuario e intentos fallidos"
        sistema.authService.sessionManager -> sistema.authService.authRepo "Guarda el hash de la sesión"
        sistema.authService.verificationTokens -> sistema.authService.authRepo "Guarda y consume el hash del token"
        sistema.authService.userManager -> sistema.authService.authRepo "Lee y escribe usuarios"
        sistema.authService.authRepo -> sistema.dbAuth "Lee y escribe en auth_db" "MongoDB"
        sistema.authService.authApi -> sistema.authService.secretProvider "Pide credenciales del tramo y clave JWT"
        sistema.authService.secretProvider -> sistema.secretsManager "Lee secretos por referencia (caché 60 s)" "HTTP (clave de servicio)"

        // =====================================================
        // COMPONENTES C3 - ORDERS
        // =====================================================
        sistema.apiGateway -> sistema.ordersService.ordersApi "Enruta pedidos, despacho, reservas y reporte" "HTTP/JSON"
        sistema.graphqlGateway -> sistema.ordersService.ordersApi "Lee y anula pedidos (gql-orders)" "HTTP/JSON"
        sistema.paymentsService -> sistema.ordersService.ordersApi "GET /internal/orders/{id} (monto real)" "HTTP/JSON"
        sistema.ordersService.ordersApi -> sistema.ordersService.accessPolicy "Comprueba rol y propiedad"
        sistema.ordersService.accessPolicy -> sistema.ordersService.orderWorkflow "Pedidos autorizados"
        sistema.ordersService.accessPolicy -> sistema.ordersService.dispatchModule "Despacho (cajero o administrador)"
        sistema.ordersService.accessPolicy -> sistema.ordersService.reservationsModule "Reservas"
        sistema.ordersService.accessPolicy -> sistema.ordersService.salesReport "Reporte (solo administrador)"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.clientsAdapter "Obtiene datos del cliente"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.inventoryAdapter "Reserva o libera stock"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.ordersRepo "Persiste pedido y transiciones"
        sistema.ordersService.dispatchModule -> sistema.ordersService.ordersRepo "Aplica la transición de despacho"
        sistema.ordersService.reservationsModule -> sistema.ordersService.ordersRepo "Guarda la reserva"
        sistema.ordersService.reservationsModule -> sistema.ordersService.outboxPublisher "Encola correo de reserva"
        sistema.ordersService.salesReport -> sistema.ordersService.ordersRepo "Agrega pedidos pagados"
        sistema.activemq -> sistema.ordersService.paymentEventConsumer "Entrega pago.aprobado" "STOMP"
        sistema.ordersService.paymentEventConsumer -> sistema.ordersService.orderWorkflow "Marca PAGADO (idempotente por event_id)"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.receiptIssuer "Pedido PAGADO: emite la boleta"
        sistema.ordersService.receiptIssuer -> sistema.ordersService.outboxPublisher "Encola el correo con la boleta"
        sistema.ordersService.receiptIssuer -> sistema.ordersService.ordersRepo "Guarda la boleta correlativa"
        sistema.ordersService.outboxPublisher -> sistema.ordersService.ordersRepo "Lee y marca el outbox"
        sistema.ordersService.outboxPublisher -> sistema.activemq "Publica notificaciones.correo" "STOMP"
        sistema.ordersService.expirationJob -> sistema.ordersService.orderWorkflow "Anula CREADO sin pago tras 30 min"
        sistema.ordersService.inventoryAdapter -> sistema.inventoryService "POST /internal/reserve y /internal/release" "HTTP/JSON"
        sistema.ordersService.clientsAdapter -> sistema.clientsService "GET /internal/clients/*" "HTTP/JSON"
        sistema.ordersService.ordersRepo -> sistema.dbOrders "Lee y escribe en orders_db" "MongoDB"

        // =====================================================
        // COMPONENTES C3 - PAYMENTS
        // =====================================================
        sistema.apiGateway -> sistema.paymentsService.paymentsApi "Inicio de pago, consulta y webhook" "HTTP/JSON"
        sistema.graphqlGateway -> sistema.paymentsService.paymentsApi "Lee pagos por lote (gql-payments)" "HTTP/JSON"
        sistema.paymentsService.paymentsApi -> sistema.paymentsService.checkoutBuilder "POST /payments"
        sistema.paymentsService.paymentsApi -> sistema.paymentsService.webhookVerifier "POST /webhooks/provider"
        sistema.paymentsService.checkoutBuilder -> sistema.paymentsService.ordersClient "Pide el monto real"
        sistema.paymentsService.checkoutBuilder -> sistema.paymentsService.paymentsRepo "Guarda el pago PENDIENTE"
        sistema.paymentsService.ordersClient -> sistema.ordersService.ordersApi "GET /internal/orders/{id}" "HTTP/JSON"
        sistema.paymentsService.webhookVerifier -> sistema.paymentsService.secretProvider "Pide prov-webhook"
        sistema.paymentsService.webhookVerifier -> sistema.paymentsService.idempotency "Firma, ventana y monto válidos"
        sistema.paymentsService.idempotency -> sistema.paymentsService.paymentsRepo "Registra el event_id y aprueba el pago"
        sistema.paymentsService.idempotency -> sistema.paymentsService.eventPublisher "Aviso nuevo: publica pago.aprobado"
        sistema.paymentsService.eventPublisher -> sistema.activemq "Publica pago.aprobado" "STOMP"
        sistema.paymentsService.secretProvider -> sistema.secretsManager "Lee secretos por referencia (caché 60 s)" "HTTP (clave de servicio)"
        sistema.paymentsService.paymentsRepo -> sistema.dbPayments "Lee y escribe en payments_db" "MongoDB"

        // =====================================================
        // COMPONENTES C3 - GRAPHQL GATEWAY
        // =====================================================
        sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Remite la operación GraphQL con JWT de 30 s" "HTTP/GraphQL"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryLimits "Verifica profundidad, costo e introspección"
        sistema.graphqlGateway.queryLimits -> sistema.graphqlGateway.fieldAccess "Consulta válida: comprueba campos"
        sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.resolvers "Campos autorizados"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.batchLoaders "Agrupa productos y pagos"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.upstreamClient "Pide pedidos"
        sistema.graphqlGateway.batchLoaders -> sistema.graphqlGateway.upstreamClient "Una llamada por lote"
        sistema.graphqlGateway.upstreamClient -> sistema.ordersService "GET /orders/{id}, GET /orders y POST /orders/{id}/cancel" "HTTP/JSON"
        sistema.graphqlGateway.upstreamClient -> sistema.inventoryService "GET /products?slugs=..." "HTTP/JSON"
        sistema.graphqlGateway.upstreamClient -> sistema.paymentsService "GET /payments/by-orders?ids=..." "HTTP/JSON"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "Entrega datos y errores parciales"

        // =====================================================
        // RESPUESTAS EXPLÍCITAS (usadas por las vistas dinámicas)
        // =====================================================
        pasarela -> sistema.frontend "Respuesta" "HTTP"
        sistema.apiGateway -> pasarela "Respuesta" "HTTP/JSON"
        sistema.apiGateway -> sistema.frontend "Respuesta" "HTTP/JSON"
        sistema.authService -> sistema.apiGateway "Respuesta" "HTTP/JSON (gw-auth)"
        sistema.authService -> sistema.clientsService "Respuesta" "HTTP/JSON (auth-clients)"
        sistema.clientsService -> sistema.apiGateway "Respuesta" "HTTP/JSON (gw-clients)"
        sistema.clientsService -> sistema.ordersService "Respuesta" "HTTP/JSON (orders-clients)"
        sistema.dbAuth -> sistema.authService "Respuesta" "MongoDB"
        sistema.dbInventory -> sistema.inventoryService "Respuesta" "MongoDB"
        sistema.dbOrders -> sistema.ordersService "Respuesta" "MongoDB"
        sistema.frontend -> administrador "Respuesta" "Navegador web"
        sistema.frontend -> cajero "Respuesta" "Navegador web"
        sistema.frontend -> cliente "Respuesta" "Navegador web"
        sistema.frontend -> visitante "Respuesta" "Navegador web"
        sistema.graphqlGateway -> sistema.apiGateway "Respuesta" "HTTP/GraphQL (gw-graphql)"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.apiGateway "Respuesta" "HTTP/GraphQL"
        sistema.graphqlGateway.queryLimits -> sistema.graphqlGateway.graphqlEndpoint "Respuesta"
        sistema.inventoryService -> sistema.apiGateway "Respuesta" "HTTP/JSON (gw-inventory)"
        sistema.inventoryService -> sistema.graphqlGateway "Respuesta" "HTTP/JSON (gql-inventory)"
        sistema.inventoryService -> sistema.ordersService "Respuesta" "HTTP/JSON (orders-inventory)"
        sistema.ordersService -> sistema.apiGateway "Respuesta" "HTTP/JSON (gw-orders)"
        sistema.ordersService -> sistema.graphqlGateway "Respuesta" "HTTP/JSON (gql-orders)"
        sistema.ordersService -> sistema.paymentsService "Respuesta" "HTTP/JSON (orders-payments)"
        sistema.paymentsService -> sistema.apiGateway "Respuesta" "HTTP/JSON (gw-payments)"
        sistema.paymentsService -> sistema.graphqlGateway "Respuesta" "HTTP/JSON (gql-payments)"

        // =====================================================
        // DESPLIEGUE (Módulo 10): Docker Compose en el equipo de desarrollo
        // =====================================================
        local = deploymentEnvironment "Docker_Compose_Local" {
            deploymentNode "Equipo de desarrollo" "Notebook con Windows 11 Home; frontend y backend en la misma máquina." "Windows 11 (AMD Ryzen 5 4600H, 11,4 GB RAM)" {
                tags "ZonaEntorno"

                deploymentNode "XAMPP" "Sirve el frontend en el puerto 8080; el navegador llama al gateway en localhost:8000." "Apache + PHP" {
                    tags "ZonaCliente"
                    containerInstance sistema.frontend
                }

                deploymentNode "Docker Desktop" "Ejecuta los 12 contenedores con health check; sistema de archivos de solo lectura, sin capacidades de Linux ni escalada de privilegios." "Docker Engine 29.9.2 sobre WSL 2" {

                    deploymentNode "Red «public»" "Red con puertos publicados al host: solo 8000 (gateway) y 9000 (pasarela)." "Docker network" {
                        tags "ZonaPublica"
                        deploymentNode "Contenedor gateway" "Único punto de entrada; también está conectado a la red privada." "Docker container (puerto 8000)" {
                            containerInstance sistema.apiGateway
                        }
                        deploymentNode "Contenedor provider-sim" "Pasarela simulada, tratada como tercero externo." "Docker container (puerto 9000)" {
                            softwareSystemInstance pasarela
                        }
                    }

                    deploymentNode "Red «private»" "Red con internal: true: sin puertos publicados y sin salida a Internet." "Docker network" {
                        tags "ZonaPrivada"
                        deploymentNode "Contenedor auth" "" "Docker container (puerto 8100)" {
                            containerInstance sistema.authService
                        }
                        deploymentNode "Contenedor secrets-manager" "Único que monta el volumen con store.json." "Docker container (puerto 8200)" {
                            containerInstance sistema.secretsManager
                        }
                        deploymentNode "Contenedor clients" "" "Docker container (puerto 8300)" {
                            containerInstance sistema.clientsService
                        }
                        deploymentNode "Contenedor inventory" "" "Docker container (puerto 8400)" {
                            containerInstance sistema.inventoryService
                        }
                        deploymentNode "Contenedor orders" "" "Docker container (puerto 8500)" {
                            containerInstance sistema.ordersService
                        }
                        deploymentNode "Contenedor payments" "" "Docker container (puerto 8600)" {
                            containerInstance sistema.paymentsService
                        }
                        deploymentNode "Contenedor graphql-gateway" "" "Docker container (puerto 8700)" {
                            containerInstance sistema.graphqlGateway
                        }
                        deploymentNode "Contenedor notifier" "Escribe en la carpeta mail-outbox." "Docker container (puerto 8800)" {
                            containerInstance sistema.notifierService
                            containerInstance sistema.mailOutbox
                        }
                        deploymentNode "Contenedor activemq" "Un usuario por servicio y permisos por cola." "Docker container (puerto 61613)" {
                            containerInstance sistema.activemq
                        }
                        deploymentNode "Contenedor mongo" "Una base y un usuario por servicio, con volumen persistente." "Docker container (puerto 27017)" {
                            containerInstance sistema.dbAuth
                            containerInstance sistema.dbClients
                            containerInstance sistema.dbInventory
                            containerInstance sistema.dbOrders
                            containerInstance sistema.dbPayments
                        }
                    }
                }
            }
        }
    }

    views {
        systemContext sistema "C1_Contexto_Al_Sahara" "Contexto del sistema Al Sahara: actores y pasarela de pago externa." {
            title "C1 - Contexto del sistema Al Sahara"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores_Al_Sahara" "Frontend, gateways, microservicios, mensajería y bases de datos." {
            title "C2 - Contenedores de Al Sahara"
            include *
            autoLayout lr
        }

        // Recortes del mismo modelo (no son otros sistemas).
        container sistema "C2_Catalogo" "Recorrido estructural de la consulta del catálogo." {
            title "C2 - Catálogo"
            include visitante sistema.frontend sistema.apiGateway sistema.inventoryService sistema.dbInventory
            autoLayout lr
        }

        container sistema "C2_Compra_y_Pago" "Recorrido estructural de pedido, pago, webhook, boleta y correo." {
            title "C2 - Compra, pago y boleta"
            include cliente pasarela sistema.frontend sistema.apiGateway sistema.authService sistema.ordersService sistema.inventoryService sistema.paymentsService sistema.activemq sistema.notifierService sistema.mailOutbox sistema.dbOrders sistema.dbPayments
            autoLayout lr
        }

        container sistema "C2_Secretos" "Quién lee secretos del gestor y quién los rota." {
            title "C2 - Gestión de secretos"
            include operador sistema.secretsManager sistema.apiGateway sistema.graphqlGateway sistema.authService sistema.clientsService sistema.inventoryService sistema.ordersService sistema.paymentsService sistema.notifierService
            autoLayout lr
        }

        component sistema.apiGateway "C3_API_Gateway" "Componentes internos del API Gateway público." {
            title "C3 - API Gateway (Origin, rate-limit, sesión y rol)"
            include *
            autoLayout lr
        }

        component sistema.authService "C3_Auth_Service" "Credenciales, sesiones, tokens de verificación y usuarios." {
            title "C3 - Auth Service"
            include *
            autoLayout lr
        }

        component sistema.ordersService "C3_Orders" "Propiedad, flujo del pedido, boleta, despacho, reservas, reporte y eventos." {
            title "C3 - orders"
            include *
            autoLayout lr
        }

        component sistema.paymentsService "C3_Payments" "Inicio del pago y verificación del webhook firmado." {
            title "C3 - payments"
            include *
            autoLayout lr
        }

        component sistema.graphqlGateway "C3_GraphQL" "Límites, autorización por campo, resolvers y batching." {
            title "C3 - GraphQL Gateway"
            include *
            autoLayout lr
        }

        // =====================================================
        // VISTAS DINÁMICAS
        // =====================================================
        dynamic sistema "D_F01_Catalogo" "Consulta anónima del catálogo (S01, RF7)." {
            title "F01 - Consulta de la carta (anónimo)"
            1: visitante -> sistema.frontend "Abre la carta (index.php)"
            2: sistema.frontend -> sistema.apiGateway "GET /api/v1/products?available=true"
            3: sistema.apiGateway -> sistema.inventoryService "GET /products con X-Caller-Key gw-inventory"
            4: sistema.inventoryService -> sistema.dbInventory "Busca platos activos"
            5: sistema.dbInventory -> sistema.inventoryService "Devuelve los platos"
            6: sistema.inventoryService -> sistema.apiGateway "Solo campos públicos: sin stock ni activo"
            7: sistema.apiGateway -> sistema.frontend "200 con el listado"
            8: sistema.frontend -> visitante "Muestra la carta"
            autoLayout lr
        }

        dynamic sistema "D_F02_Registro" "Registro de cliente con compensación y correo de verificación (S03, RF5 y RF11)." {
            title "F02 - Registro de cliente"
            1: visitante -> sistema.frontend "Completa el formulario de registro"
            2: sistema.frontend -> sistema.apiGateway "POST /auth/register (Origin permitido)"
            3: sistema.apiGateway -> sistema.clientsService "POST /clients/register"
            4: sistema.clientsService -> sistema.authService "POST /users: crea la cuenta"
            5: sistema.authService -> sistema.dbAuth "Guarda hash Argon2id y token de verificación"
            6: sistema.authService -> sistema.clientsService "Devuelve el id de la cuenta"
            7: sistema.clientsService -> sistema.dbClients "Guarda el perfil (RUN único)"
            8: sistema.clientsService -> sistema.activemq "Publica el correo de verificación"
            9: sistema.activemq -> sistema.notifierService "Entrega notificaciones.correo"
            10: sistema.notifierService -> sistema.mailOutbox "Escribe el correo en outbox.jsonl"
            11: sistema.clientsService -> sistema.apiGateway "201 con el id del cliente"
            12: sistema.apiGateway -> sistema.frontend "Responde 201"
            13: sistema.frontend -> visitante "Pide verificar el correo"
            autoLayout lr
        }

        dynamic sistema "D_F03_Login" "Inicio de sesión con cookie HttpOnly (S05, RF12)." {
            title "F03 - Inicio de sesión"
            1: visitante -> sistema.frontend "Envía correo y contraseña"
            2: sistema.frontend -> sistema.apiGateway "POST /auth/login"
            3: sistema.apiGateway -> sistema.authService "POST /login con gw-auth"
            4: sistema.authService -> sistema.dbAuth "Busca usuario, compara Argon2id y cuenta intentos"
            5: sistema.dbAuth -> sistema.authService "Devuelve el registro"
            6: sistema.authService -> sistema.apiGateway "Token de sesión y rol"
            7: sistema.apiGateway -> sistema.frontend "200 {role, user_id} + Set-Cookie HttpOnly SameSite=Lax"
            8: sistema.frontend -> visitante "Redirige según el rol"
            autoLayout lr
        }

        dynamic sistema "D_F04_Crear_Pedido" "Pedido con precios del servidor y reserva atómica de stock (S18, RF1)." {
            title "F04 - Creación de pedido con reserva de stock"
            1: cliente -> sistema.frontend "Confirma el carrito (slugs y cantidades)"
            2: sistema.frontend -> sistema.apiGateway "POST /orders"
            3: sistema.apiGateway -> sistema.authService "GET /session/verify con la cookie"
            4: sistema.authService -> sistema.apiGateway "Principal: user_id y rol cliente"
            5: sistema.apiGateway -> sistema.ordersService "POST /orders con X-Caller-Key y JWT de 30 s (aud=orders)"
            6: sistema.ordersService -> sistema.clientsService "Obtiene los datos del cliente"
            7: sistema.clientsService -> sistema.ordersService "Devuelve nombre y teléfono"
            8: sistema.ordersService -> sistema.inventoryService "POST /internal/reserve (todo o nada)"
            9: sistema.inventoryService -> sistema.ordersService "Precios vigentes y reserva confirmada"
            10: sistema.ordersService -> sistema.dbOrders "Guarda el pedido CREADO con el total del servidor"
            11: sistema.ordersService -> sistema.apiGateway "201 con el pedido"
            12: sistema.apiGateway -> sistema.frontend "Responde 201"
            13: sistema.frontend -> cliente "Muestra el resumen y el botón Pagar"
            autoLayout lr
        }

        dynamic sistema "D_F05_Iniciar_Pago" "El monto lo decide el servidor; el navegador solo envía el orderId (S22, RF2)." {
            title "F05 - Inicio del pago"
            1: cliente -> sistema.frontend "Presiona Pagar (pago.php)"
            2: sistema.frontend -> sistema.apiGateway "POST /payments {orderId}"
            3: sistema.apiGateway -> sistema.paymentsService "POST /payments (sin monto)"
            4: sistema.paymentsService -> sistema.ordersService "GET /internal/orders/{id}: monto real"
            5: sistema.ordersService -> sistema.paymentsService "Monto y estado del pedido"
            6: sistema.paymentsService -> sistema.dbPayments "Guarda el pago PENDIENTE"
            7: sistema.paymentsService -> sistema.apiGateway "201 con checkoutUrl firmada (HMAC)"
            8: sistema.apiGateway -> sistema.frontend "Devuelve checkoutUrl"
            9: sistema.frontend -> pasarela "Redirige a la pasarela"
            10: cliente -> pasarela "Aprueba el pago"
            autoLayout lr
        }

        dynamic sistema "D_F06_Confirmacion_Webhook" "Webhook firmado, evento pago.aprobado, boleta correlativa y correo (S23, RF2 y RF8)." {
            title "F06 - Confirmación asíncrona: webhook, boleta y correo"
            1: pasarela -> sistema.apiGateway "POST /webhooks/payments con X-Signature HMAC"
            2: sistema.apiGateway -> sistema.paymentsService "Reenvía sin exigir sesión ni Origin"
            3: sistema.paymentsService -> sistema.dbPayments "Valida y registra event_id; pago APROBADO"
            4: sistema.paymentsService -> sistema.activemq "Publica pago.aprobado (outbox)"
            5: sistema.activemq -> sistema.ordersService "Entrega pago.aprobado"
            6: sistema.ordersService -> sistema.dbOrders "Pasa a PAGADO y emite la boleta N.º correlativa"
            7: sistema.ordersService -> sistema.activemq "Publica notificaciones.correo"
            8: sistema.activemq -> sistema.notifierService "Entrega el correo con la boleta"
            9: sistema.notifierService -> sistema.mailOutbox "Escribe el correo en outbox.jsonl"
            10: pasarela -> sistema.frontend "303 hacia pago.php"
            autoLayout lr
        }

        dynamic sistema.paymentsService "D_F06_Webhook_C3" "Verificación del webhook dentro de payments (firma, ventana, monto e idempotencia)." {
            title "F06 - Webhook firmado: componentes internos de payments"
            1: sistema.apiGateway -> sistema.paymentsService.paymentsApi "POST /webhooks/provider"
            2: sistema.paymentsService.paymentsApi -> sistema.paymentsService.webhookVerifier "Valida firma, ventana de 5 min y monto"
            3: sistema.paymentsService.webhookVerifier -> sistema.paymentsService.secretProvider "Pide prov-webhook"
            4: sistema.paymentsService.secretProvider -> sistema.secretsManager "Lee el secreto HMAC"
            5: sistema.paymentsService.webhookVerifier -> sistema.paymentsService.idempotency "Aviso válido: comprueba event_id"
            6: sistema.paymentsService.idempotency -> sistema.paymentsService.paymentsRepo "Registra el evento una sola vez y aprueba el pago"
            7: sistema.paymentsService.paymentsRepo -> sistema.dbPayments "Guarda evento y pago"
            8: sistema.paymentsService.idempotency -> sistema.paymentsService.eventPublisher "Evento nuevo: publica pago.aprobado"
            9: sistema.paymentsService.eventPublisher -> sistema.activemq "pago.aprobado"
            autoLayout lr
        }

        dynamic sistema "D_F07_Webhook_Forjado" "Un aviso sin firma o con firma inválida no cambia el pedido (validación 6)." {
            title "F07 - Pago forjado: webhook rechazado"
            1: pasarela -> sistema.apiGateway "POST /webhooks/payments sin firma o con firma inválida"
            2: sistema.apiGateway -> sistema.paymentsService "Reenvía el aviso"
            3: sistema.paymentsService -> sistema.apiGateway "401 Firma no válida; no escribe ni publica nada"
            4: sistema.apiGateway -> pasarela "401"
            autoLayout lr
        }

        dynamic sistema "D_F08_Pedido_Ajeno" "Propiedad del recurso: un pedido ajeno responde 404 (validación 4)." {
            title "F08 - Consulta de pedido ajeno"
            1: cliente -> sistema.frontend "Intenta abrir el pedido de otro cliente"
            2: sistema.frontend -> sistema.apiGateway "GET /orders/{idAjeno}"
            3: sistema.apiGateway -> sistema.authService "Verifica la sesión"
            4: sistema.authService -> sistema.apiGateway "Sesión válida (no implica acceso al pedido)"
            5: sistema.apiGateway -> sistema.ordersService "GET /orders/{id} con JWT del usuario"
            6: sistema.ordersService -> sistema.dbOrders "Busca por id y user_id"
            7: sistema.dbOrders -> sistema.ordersService "Sin resultado"
            8: sistema.ordersService -> sistema.apiGateway "404, igual que si no existiera"
            9: sistema.apiGateway -> sistema.frontend "Responde 404"
            10: sistema.frontend -> cliente "Muestra no encontrado"
            autoLayout lr
        }

        dynamic sistema "D_F09_GraphQL_Resumen" "Agregación de orders, inventory y payments por lote (S33)." {
            title "F09 - GraphQL: resumenPedido"
            1: cliente -> sistema.frontend "Vuelve de la pasarela a pago.php"
            2: sistema.frontend -> sistema.apiGateway "POST /graphql resumenPedido(id)"
            3: sistema.apiGateway -> sistema.graphqlGateway "Remite la consulta con JWT de 30 s"
            4: sistema.graphqlGateway -> sistema.ordersService "GET /orders/{id} (gql-orders)"
            5: sistema.ordersService -> sistema.graphqlGateway "Pedido del dueño o 404 (null)"
            6: sistema.graphqlGateway -> sistema.inventoryService "GET /products?slugs=... (un lote)"
            6: sistema.graphqlGateway -> sistema.paymentsService "GET /payments/by-orders (un lote)"
            7: sistema.inventoryService -> sistema.graphqlGateway "Devuelve productos"
            7: sistema.paymentsService -> sistema.graphqlGateway "Devuelve el pago"
            8: sistema.graphqlGateway -> sistema.apiGateway "Respuesta compuesta (errores parciales en errors[])"
            9: sistema.apiGateway -> sistema.frontend "200 con estado, boleta y pago"
            10: sistema.frontend -> cliente "Muestra el resumen del pedido"
            autoLayout lr
        }

        dynamic sistema.graphqlGateway "D_F09_GraphQL_Limite_C3" "Una consulta de costo 9805 se rechaza antes de ejecutar resolvers." {
            title "F09 - GraphQL: consulta que excede el costo"
            1: sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Envía una consulta de costo 9805"
            2: sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryLimits "Calcula costo y profundidad"
            3: sistema.graphqlGateway.queryLimits -> sistema.graphqlGateway.graphqlEndpoint "Rechaza: COST_LIMIT (máximo 1000)"
            4: sistema.graphqlGateway.graphqlEndpoint -> sistema.apiGateway "400 sin llamar a resolvers ni a servicios"
            autoLayout lr
        }

        dynamic sistema.graphqlGateway "D_F09_GraphQL_Campo_C3" "Un cliente no ve los campos reservados al personal." {
            title "F09 - GraphQL: campo solo para personal"
            1: sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "misPedidos pidiendo cliente y requiereReembolso"
            2: sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryLimits "Verifica límites"
            3: sistema.graphqlGateway.queryLimits -> sistema.graphqlGateway.fieldAccess "Consulta válida"
            4: sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.resolvers "Autoriza el resto de los campos"
            5: sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.upstreamClient "Pide los pedidos propios"
            6: sistema.graphqlGateway.upstreamClient -> sistema.ordersService "GET /orders (orders filtra por dueño)"
            7: sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "cliente = null + error FORBIDDEN"
            autoLayout lr
        }

        dynamic sistema "D_F10_Reporte_Admin" "Reporte de ventas solo para el administrador (S26, RF9)." {
            title "F10 - Reporte de ventas (administrador)"
            1: administrador -> sistema.frontend "Pide el reporte del mes"
            2: sistema.frontend -> sistema.apiGateway "GET /reports/sales?desde&hasta"
            3: sistema.apiGateway -> sistema.authService "Verifica la sesión"
            4: sistema.authService -> sistema.apiGateway "Rol administrador"
            5: sistema.apiGateway -> sistema.ordersService "GET /reports/sales"
            6: sistema.ordersService -> sistema.dbOrders "Agrega solo pedidos pagados"
            7: sistema.ordersService -> sistema.apiGateway "Totales, ticket promedio y platos más vendidos"
            8: sistema.apiGateway -> sistema.frontend "200 sin datos personales"
            9: sistema.frontend -> administrador "Muestra el reporte"
            autoLayout lr
        }

        dynamic sistema "D_F10_Reporte_Denegado" "Rol insuficiente: el gateway rechaza antes de llegar a orders (Figura 20)." {
            title "F10 - Reporte de ventas: cajero rechazado"
            1: cajero -> sistema.frontend "Intenta abrir el reporte"
            2: sistema.frontend -> sistema.apiGateway "GET /reports/sales"
            3: sistema.apiGateway -> sistema.authService "Verifica la sesión"
            4: sistema.authService -> sistema.apiGateway "Rol cajero"
            5: sistema.apiGateway -> sistema.frontend "403 Sin permiso; orders no recibe la solicitud"
            6: sistema.frontend -> cajero "Muestra acceso denegado"
            autoLayout lr
        }

        dynamic sistema "D_F11_Despacho" "Orden de despacho: conductor obligatorio y transición atómica (S28, RF13)." {
            title "F11 - Despacho de un pedido a domicilio"
            1: cajero -> sistema.frontend "Asigna conductor y despacha"
            2: sistema.frontend -> sistema.apiGateway "PATCH /dispatch/{id} {EN_CAMINO, conductor}"
            3: sistema.apiGateway -> sistema.authService "Verifica la sesión"
            4: sistema.authService -> sistema.apiGateway "Rol cajero"
            5: sistema.apiGateway -> sistema.ordersService "PATCH /dispatch/{id}"
            6: sistema.ordersService -> sistema.dbOrders "Transición atómica LISTO a EN_CAMINO"
            7: sistema.ordersService -> sistema.apiGateway "200 con conductor y hora de salida"
            8: sistema.apiGateway -> sistema.frontend "Responde 200"
            9: sistema.frontend -> cajero "Muestra el pedido EN_CAMINO"
            autoLayout lr
        }

        dynamic sistema "D_F12_Reserva" "Reserva de mesa anónima con correo por outbox (S30, RF14)." {
            title "F12 - Reserva de mesa"
            1: visitante -> sistema.frontend "Completa el formulario de reserva"
            2: sistema.frontend -> sistema.apiGateway "POST /reservations (sesión opcional)"
            3: sistema.apiGateway -> sistema.ordersService "POST /reservations"
            4: sistema.ordersService -> sistema.dbOrders "Guarda la reserva PENDIENTE y el outbox"
            5: sistema.ordersService -> sistema.apiGateway "201 PENDIENTE"
            6: sistema.apiGateway -> sistema.frontend "Responde 201"
            7: sistema.frontend -> visitante "Confirma que la solicitud fue recibida"
            8: sistema.ordersService -> sistema.activemq "Publica notificaciones.correo"
            9: sistema.activemq -> sistema.notifierService "Entrega el correo"
            10: sistema.notifierService -> sistema.mailOutbox "Escribe 'tu reserva está pendiente'"
            autoLayout lr
        }

        // =====================================================
        // VISTA DE DESPLIEGUE
        // =====================================================
        deployment sistema local "DEP_Docker_Compose" "12 contenedores en dos redes Docker; solo el gateway y la pasarela publican puerto." {
            title "Despliegue - Docker Compose (redes public y private)"
            include *
            autoLayout lr
        }

        styles {
            element "Deployment Node" {
                background #E9EFF5
                color #213F56
                stroke #8FA5B7
            }
            element "ZonaEntorno" {
                background #F4F6F8
                color #213F56
            }
            element "ZonaCliente" {
                background #F1F5F9
                color #173B5D
            }
            element "ZonaPublica" {
                background #DCEAF7
                color #173B5D
            }
            element "ZonaPrivada" {
                background #E5EEE8
                color #20513D
            }
            element "Person" {
                shape person
                background #56718A
                color #FFFFFF
            }
            element "Software System" {
                shape roundedbox
                background #0C527A
                color #FFFFFF
            }
            element "SistemaEvaluado" {
                background #173B5D
                color #FFFFFF
            }
            element "SistemaExterno" {
                background #7F8C8D
                color #FFFFFF
            }
            element "Container" {
                shape roundedbox
                background #E3ECF5
                color #173B5D
            }
            element "Frontend" {
                shape webbrowser
                background #CDE5F7
                color #153E5B
            }
            element "Gateway" {
                background #2B6289
                color #FFFFFF
            }
            element "Seguridad" {
                background #3F6171
                color #FFFFFF
            }
            element "Privado" {
                background #D5E8EF
                color #173B5D
            }
            element "Broker" {
                shape pipe
                background #E67E22
                color #FFFFFF
            }
            element "Archivo" {
                shape folder
                background #F1EDE7
                color #544633
            }
            element "BaseDatos" {
                shape cylinder
                background #E5EAF0
                color #243F56
            }

            // C3: colores funcionales para componentes internos.
            element "Component" {
                shape roundedbox
                background #EDF3F7
                color #173B5D
            }
            element "EntradaC3" {
                background #D3E9F7
                color #153F62
            }
            element "ControlC3" {
                background #DBE4EC
                color #213F56
            }
            element "AplicacionC3" {
                background #D7E9DE
                color #20533E
            }
            element "IntegracionC3" {
                background #E9E2F2
                color #4A3666
            }
            element "PersistenciaC3" {
                background #E9EBEE
                color #334454
            }
            element "ErrorC3" {
                background #F2E6DB
                color #70462C
            }
            relationship "Relationship" {
                color #60758A
                thickness 2
            }
        }
    }
}
