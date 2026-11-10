# Evidencias faltantes del informe: RF4, RF6, RF7, RF9, RF13 y GraphQL.
#
# Uso (PowerShell, desde la carpeta Evaluacion2, con el sistema levantado y seed_test_data.py ya ejecutado):
#   .\scripts\evidencias_faltantes.ps1                 # todos los bloques
#   .\scripts\evidencias_faltantes.ps1 -Solo RF9,GQL   # solo algunos (RF4, RF6, RF7, RF9, RF13, GQL)
# Si Windows bloquea el script:  powershell -ExecutionPolicy Bypass -File .\scripts\evidencias_faltantes.ps1
#
# Las claves de admin y cajero se leen de secrets/seed.env y nunca se imprimen. Los correos se muestran
# enmascarados y no se muestran cookies, asi que la salida se puede capturar tal cual para el informe.
# Cada bloque termina con el nombre sugerido para la captura.

param([string[]]$Solo = @("RF4", "RF6", "RF7", "RF9", "RF13", "GQL"))

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Base     = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:8000/api/v1" }
$Origin   = if ($env:ORIGIN) { $env:ORIGIN } else { "http://localhost:8080" }   # debe estar en ALLOWED_ORIGINS
$Provider = if ($env:PROVIDER_URL) { $env:PROVIDER_URL } else { "http://localhost:9000" }
$Comuna   = "Vi$([char]0x00F1)a del Mar"   # unica comuna con cobertura (coverage.json)

# ------------------------------------------------------------------ utilidades
function Leer-SeedEnv {
    $f = Join-Path (Get-Location) "secrets\seed.env"
    if (-not (Test-Path $f)) { throw "No encuentro $f. Ejecuta el script desde la carpeta Evaluacion2." }
    $v = @{}
    Get-Content $f | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } | ForEach-Object { $v[$Matches[1]] = $Matches[2].Trim() }
    return $v
}

function Ocultar([string]$texto) {
    # Enmascara correos (a***@dominio) para que la captura no muestre datos personales.
    return [regex]::Replace($texto, '([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@', '$1***@')
}

function Titulo([string]$t) { Write-Host ""; Write-Host ("=" * 78) -ForegroundColor DarkGray; Write-Host $t -ForegroundColor Cyan }
function Captura([string]$archivo) { Write-Host "--> Captura esta salida como images\$archivo" -ForegroundColor Yellow }

function Llamar {
    param([string]$Metodo, [string]$Ruta, $Cuerpo = $null, $Sesion = $null, [string]$Etiqueta = "", [switch]$Silencio,
          [object[]]$Campos = $null,   # Campos: muestra solo esas propiedades (salida corta para la captura)
          [switch]$Compacto)           # Compacto: el JSON en una sola linea
    $p = @{ Uri = "$Base$Ruta"; Method = $Metodo; Headers = @{ Origin = $Origin }; UseBasicParsing = $true }
    if ($Sesion) { $p.WebSession = $Sesion }
    if ($null -ne $Cuerpo) {
        $p.ContentType = "application/json; charset=utf-8"
        $p.Body = [Text.Encoding]::UTF8.GetBytes(($Cuerpo | ConvertTo-Json -Depth 8 -Compress))
    }
    try {
        $r = Invoke-WebRequest @p
        $codigo = [int]$r.StatusCode
        $texto = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
    } catch {
        if (-not $_.Exception.Response) { throw }
        $codigo = [int]$_.Exception.Response.StatusCode
        $texto = $_.ErrorDetails.Message
    }
    $json = $null
    if ($texto) { try { $json = $texto | ConvertFrom-Json } catch { } }
    if (-not $Silencio) {
        $color = if ($codigo -lt 300) { "Green" } else { "Red" }
        Write-Host ("{0,-6} {1} -> HTTP {2}  {3}" -f $Metodo, $Ruta, $codigo, $Etiqueta) -ForegroundColor $color
        if ($json -and $Campos) { Write-Host (Ocultar ($json | Select-Object $Campos | Format-List | Out-String).Trim()) }
        elseif ($json -and $Compacto) { Write-Host (Ocultar ($json | ConvertTo-Json -Depth 8 -Compress)) }
        elseif ($json) { Write-Host (Ocultar ($json | ConvertTo-Json -Depth 8)) }
    }
    return [pscustomobject]@{ Codigo = $codigo; Json = $json }
}

function Iniciar-Sesion([string]$email, [string]$clave) {
    $s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $r = Llamar POST "/auth/login" @{ email = $email; password = $clave } $s -Silencio
    if ($r.Codigo -ne 200) { throw "Login fallido para $(Ocultar $email): HTTP $($r.Codigo)" }
    Write-Host ("Sesion iniciada: {0} (rol {1})" -f (Ocultar $email), $r.Json.role) -ForegroundColor DarkGray
    return $s
}

function RUN-Ficticio {
    # Numero aleatorio de 8 digitos (rango 40-49 millones, poco probable en personas reales) + digito verificador modulo 11.
    $n = Get-Random -Minimum 40000000 -Maximum 49999999
    $total = 0; $mult = 2
    foreach ($d in ([string]$n).ToCharArray()[7..0]) { $total += [int][string]$d * $mult; $mult = if ($mult -eq 7) { 2 } else { $mult + 1 } }
    $r = 11 - ($total % 11)
    $dv = if ($r -eq 11) { "0" } elseif ($r -eq 10) { "K" } else { [string]$r }
    return "$n-$dv"
}

function Primer-Cliente($sesion) {
    $r = Llamar GET "/clients?limit=1" -Sesion $sesion -Silencio
    if (-not $r.Json) { throw "No hay clientes. Ejecuta primero scripts\seed_test_data.py." }
    return @($r.Json)[0].id
}

function Pagar($sesion, [string]$orderId) {
    $r = Llamar POST "/payments" @{ orderId = $orderId } $sesion -Silencio
    if ($r.Codigo -ne 201) { throw "No se pudo iniciar el pago: HTTP $($r.Codigo)" }
    $t = [regex]::Match($r.Json.checkoutUrl, "[?&]t=([^&]+)").Groups[1].Value
    try {
        Invoke-WebRequest -Uri "$Provider/pay/result" -Method POST -Body @{ t = $t; resultado = "ok" } `
            -MaximumRedirection 0 -UseBasicParsing | Out-Null
    } catch { }  # la pasarela responde 303 hacia el frontend: no hace falta seguirla
    for ($i = 0; $i -lt 20; $i++) {
        $o = Llamar GET "/orders/$orderId" -Sesion $sesion -Silencio
        if ($o.Json.estado -eq "PAGADO") { return }
        Start-Sleep -Milliseconds 500
    }
    throw "El pedido $orderId no paso a PAGADO (revisa: docker compose logs payments orders)"
}

# ------------------------------------------------------------------ sesiones
if ($Solo.Count -eq 1) { try { Clear-Host } catch { } }   # un solo bloque: pantalla limpia para la captura
$seed = Leer-SeedEnv
$admin  = Iniciar-Sesion "admin@alsahara.cl"  $seed["SEED_ADMIN_PASSWORD"]
$cajero = Iniciar-Sesion "cajero@alsahara.cl" $seed["SEED_CAJERO_PASSWORD"]

# ------------------------------------------------------------------ RF4: venta en el local (cajero virtual)
if ($Solo -contains "RF4") {
    Titulo "RF4 - El cajero registra una venta en el local (tipo LOCAL, canal CAJA)"
    $cli = Primer-Cliente $cajero
    $o = Llamar POST "/orders" @{ tipo = "LOCAL"; clienteId = $cli; comentario = "Venta en caja";
                                  items = @(@{ slug = "shawarma-cordero"; cantidad = 1 }, @{ slug = "baklava"; cantidad = 2 }) } $cajero "(cajero)" `
                                  -Campos id, estado, tipo, total, @{ n = "items"; e = { ($_.items | ForEach-Object { "$($_.cantidad) x $($_.nombre)" }) -join ", " } }
    if ($o.Codigo -eq 201) {
        Pagar $cajero $o.Json.id
        Llamar PATCH "/orders/$($o.Json.id)/status" @{ estado = "EN_PREPARACION" } $cajero "(cocina)" -Silencio | Out-Null
        Llamar PATCH "/orders/$($o.Json.id)/status" @{ estado = "LISTO" } $cajero "(cocina)" -Silencio | Out-Null
        Llamar PATCH "/orders/$($o.Json.id)/status" @{ estado = "ENTREGADO" } $cajero "(entregado en mesa)" `
            -Campos estado, tipo, total, @{ n = "boleta"; e = { "N.o $($_.boleta.numero)" } },
                    @{ n = "historial"; e = { ($_.historial.estado) -join " -> " } } | Out-Null
    }
    Captura "rf4_venta_local.png"
}

# ------------------------------------------------------------------ RF6: registro de cliente en el local
if ($Solo -contains "RF6") {
    Titulo "RF6 - El administrador registra un cliente en el local (sin cuenta web)"
    $run = RUN-Ficticio   # RUN valido y distinto en cada ejecucion: el registro siempre responde 201
    Llamar POST "/clients" @{ run = $run; nombre = "Cliente Presencial Prueba"; fechaNacimiento = "1990-05-12"; sexo = "O";
                              telefono = "+56911112222"; direccion = "Av. Libertad 1234"; comuna = $Comuna;
                              provincia = "Valpara$([char]0x00ED)so"; region = "Valpara$([char]0x00ED)so" } $admin "(admin)" `
        -Campos id, run, nombre, telefono, email | Out-Null
    Llamar GET "/clients?q=$run" -Sesion $cajero -Etiqueta "(cajero: listado con RUN enmascarado)" `
        -Campos id, nombre, run, conCuenta | Out-Null
    Llamar POST "/clients" @{ run = "11111111-1"; nombre = "Intento Cajero"; fechaNacimiento = "1990-01-01"; sexo = "F";
                              telefono = "+56933334444" } $cajero "(cajero no puede registrar: se espera 403)" | Out-Null
    Captura "rf6_registro_local.png"
}

# ------------------------------------------------------------------ RF7: disponibilidad de productos
if ($Solo -contains "RF7") {
    Titulo "RF7 - El cajero marca un plato como no disponible y el catalogo publico lo refleja"
    $anon = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $antes = Llamar GET "/products/kunafa" -Sesion $anon -Silencio
    Write-Host ("Catalogo publico antes:   kunafa disponible = {0}" -f $antes.Json.disponible)
    Llamar PATCH "/products/kunafa/availability" @{ disponible = $false } $cajero "(cajero)" -Campos slug, nombre, disponible, stock | Out-Null
    $desp = Llamar GET "/products/kunafa" -Sesion $anon -Silencio
    Write-Host ("Catalogo publico despues: kunafa disponible = {0}" -f $desp.Json.disponible) -ForegroundColor Green
    Llamar PATCH "/products/kunafa/availability" @{ disponible = $false } $anon "(sin sesion: se espera 401)" | Out-Null
    Llamar PATCH "/products/kunafa/availability" @{ disponible = $true } $cajero "(se restablece)" -Silencio | Out-Null
    Write-Host "kunafa restablecida como disponible." -ForegroundColor DarkGray
    Captura "rf7_disponibilidad.png"
}

# ------------------------------------------------------------------ RF9: reporte de ventas
if ($Solo -contains "RF9") {
    Titulo "RF9 - Reporte de ventas: permitido al administrador, denegado al cajero"
    Write-Host "Reporte sobre datos de prueba generados con scripts\seed_test_data.py (pedidos ficticios)." -ForegroundColor DarkGray
    $hasta = Get-Date -Format "yyyy-MM-dd"
    $desde = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
    Llamar GET "/reports/sales?desde=$desde&hasta=$hasta" -Sesion $admin -Etiqueta "(admin)" `
        -Campos desde, hasta, pedidos, total, ticketPromedio,
                @{ n = "porTipo"; e = { ($_.porTipo | ForEach-Object { "$($_.tipo): $($_.pedidos) pedidos / `$$($_.total)" }) -join " | " } },
                @{ n = "top3Platos"; e = { ($_.topPlatos | Select-Object -First 3 | ForEach-Object { "$($_.nombre) ($($_.unidades))" }) -join ", " } } | Out-Null
    Llamar GET "/reports/sales?desde=$desde&hasta=$hasta" -Sesion $cajero -Etiqueta "(cajero: se espera 403)" | Out-Null
    Captura "rf9_reporte_ventas.png"
}

# ------------------------------------------------------------------ RF13: orden de despacho
if ($Solo -contains "RF13") {
    Titulo "RF13 - Despacho: sin conductor se rechaza; con conductor pasa a EN_CAMINO"
    $cli = Primer-Cliente $cajero
    $o = Llamar POST "/orders" @{ tipo = "DELIVERY"; clienteId = $cli; direccion = "Calle Valpara$([char]0x00ED)so 456"; comuna = $Comuna;
                                  items = @(@{ slug = "kebab-mixto"; cantidad = 1 }) } $cajero "(pedido a domicilio)" -Silencio
    if ($o.Codigo -ne 201) { throw "No se pudo crear el pedido de prueba: HTTP $($o.Codigo)" }
    $id = $o.Json.id
    Pagar $cajero $id
    Llamar PATCH "/orders/$id/status" @{ estado = "EN_PREPARACION" } $cajero -Silencio | Out-Null
    Llamar PATCH "/orders/$id/status" @{ estado = "LISTO" } $cajero -Silencio | Out-Null
    Write-Host "Pedido $id pagado y LISTO para despacho." -ForegroundColor DarkGray
    Llamar PATCH "/dispatch/$id" @{ estado = "EN_CAMINO" } $cajero "(sin conductor: se espera 422)" | Out-Null
    Llamar PATCH "/dispatch/$id" @{ estado = "EN_CAMINO"; conductor = "Pedro Ruiz" } $cajero "(con conductor)" `
        -Campos estado, tipo, @{ n = "despacho"; e = { $_.despacho.estado } }, @{ n = "conductor"; e = { $_.despacho.conductor } },
                @{ n = "salida"; e = { $_.despacho.salidaEn } } | Out-Null
    Captura "rf13_despacho.png"
}

# ------------------------------------------------------------------ GraphQL
if ($Solo -contains "GQL") {
    Titulo "GraphQL - consulta valida, campo restringido, costo excedido, introspeccion y puerto 8700"
    $cliente = Iniciar-Sesion "cliente01@example.cl" "Prueba1234"   # cliente ficticio de seed_test_data.py
    # Garantiza que el cliente tenga al menos un pedido propio para las consultas.
    Llamar POST "/orders" @{ tipo = "DELIVERY"; direccion = "Av. Libertad 1234"; comuna = $Comuna;
                             items = @(@{ slug = "falafel-casero"; cantidad = 1 }) } $cliente -Silencio | Out-Null

    $ok = 'query { misPedidos(limit: 1) { id estado total items { nombre cantidad producto { precio } } pago { estado } } }'
    Llamar POST "/graphql" @{ query = $ok } $cliente "(1. consulta valida del cliente)" -Compacto | Out-Null

    $restr = 'query { misPedidos(limit: 1) { id estado cliente { nombre } requiereReembolso } }'
    Llamar POST "/graphql" @{ query = $restr } $cliente "(2. campos solo para personal: null + FORBIDDEN)" -Compacto | Out-Null

    $campos = "id estado total items { nombre cantidad producto { id nombre precio disponible } } historial { estado ts } pago { estado monto }"
    $costosa = "query Costosa { " + ((1..5 | ForEach-Object { "p${_}: misPedidos(limit: 20) { $campos }" }) -join " ") + " }"
    Llamar POST "/graphql" @{ query = $costosa; operationName = "Costosa" } $cliente "(3. costo excedido: se espera COST_LIMIT)" -Compacto | Out-Null

    Llamar POST "/graphql" @{ query = 'query { __schema { types { name } } }' } $cliente "(4. introspeccion: se espera INTROSPECTION_DISABLED)" -Compacto | Out-Null

    $abierto = (Test-NetConnection -ComputerName localhost -Port 8700 -WarningAction SilentlyContinue).TcpTestSucceeded
    Write-Host ("5. Puerto 8700 (GraphQL privado) alcanzable desde el host: {0}  (se espera False)" -f $abierto) -ForegroundColor $(if ($abierto) { "Red" } else { "Green" })
    Captura "graphql_resumen.png"
}

Write-Host ""
Write-Host "Listo. Revisa que ninguna captura muestre cookies, claves ni correos completos." -ForegroundColor Cyan
