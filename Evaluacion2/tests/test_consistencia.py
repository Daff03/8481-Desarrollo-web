"""Vigila que las piezas del proyecto sigan cuadrando entre sí: versiones, puertos, referencias de secretos, compose,
Dockerfiles y llamadas del frontend. Si falla, algo se cambió en un lugar y no en el otro."""
import ast, importlib.util, json, pathlib, re, sys
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "scripts", ROOT / "gateway", ROOT / "graphql-gateway"):  # gateway importa `routes` y graphql-gateway importa `limits`
    sys.path.insert(0, str(_p))
import gen_secrets

SERVICES = ["auth", "gateway", "secrets-manager", "svc-clients", "svc-inventory", "svc-notifier", "svc-orders", "svc-payments",
            "provider-sim", "graphql-gateway"]
# carpeta del servicio → id del servicio en policy.json
SERVICE_ID = {"svc-clients": "clients", "svc-inventory": "inventory", "svc-notifier": "notifier", "svc-orders": "orders",
              "svc-payments": "payments", "auth": "auth", "gateway": "gateway", "graphql-gateway": "graphql-gateway",
              "provider-sim": "provider-sim", "secrets-manager": "secrets-manager"}
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
POLICY = json.loads((ROOT / "secrets-manager" / "policy.json").read_text(encoding="utf-8"))
REFS = POLICY["refs"]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def py_files(folder):
    return [p for p in (ROOT / folder).glob("*.py")]


def dockerfile_of(svc):
    b = svc["build"]
    ctx = b if isinstance(b, str) else b.get("context", ".")
    df = "Dockerfile" if isinstance(b, str) else b.get("dockerfile", "Dockerfile")
    return (ROOT / ctx).resolve(), (ROOT / ctx / df).resolve()


def built_services():
    return {n: s for n, s in COMPOSE["services"].items() if "build" in s}


# ------------------------------------------------------------------ versiones
def test_cada_paquete_tiene_una_sola_version_en_todo_el_proyecto():
    seen: dict[str, dict[str, list]] = {}
    for d in SERVICES:
        for line in (ROOT / d / "requirements.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([\w.]+)", line)
            assert m, f"{d}: '{line}' no está fijado con =="
            seen.setdefault(m.group(1).lower(), {}).setdefault(m.group(2), []).append(d)
    conflictos = {n: v for n, v in seen.items() if len(v) > 1}
    assert not conflictos, f"Versiones distintas del mismo paquete: {conflictos}"


def test_requirements_dev_arma_el_entorno_completo():
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    for d in SERVICES:
        assert f"-r {d}/requirements.txt" in dev, f"requirements-dev no incluye {d}"
    for pkg in ("pytest", "mongomock", "PyYAML"):
        assert re.search(rf"^{pkg}==[\w.]+$", dev, re.M), f"{pkg} debe estar fijado en requirements-dev.txt"


def test_una_sola_version_de_python_en_todas_las_imagenes():
    bases = {}
    for name, svc in built_services().items():
        first = next(l for l in dockerfile_of(svc)[1].read_text(encoding="utf-8").splitlines() if l.startswith("FROM"))
        bases[name] = first
    assert len(set(bases.values())) == 1, bases
    assert re.fullmatch(r"FROM python:3\.\d+\.\d+-slim", next(iter(bases.values()))), "fija la imagen con versión exacta (X.Y.Z-slim)"


def test_imagenes_de_terceros_con_version_exacta():
    for name, svc in COMPOSE["services"].items():
        if "image" in svc:
            assert re.search(r":\d+(\.\d+)+$", svc["image"]), f"{name}: {svc['image']} debe tener versión exacta (sin latest ni solo mayor)"


def test_python_de_las_pruebas_vs_imagen():
    img = re.search(r"python:(\d+\.\d+)", (ROOT / "auth" / "Dockerfile").read_text(encoding="utf-8")).group(1)
    actual = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual != img:
        pytest.skip(f"Las pruebas corren con Python {actual}; las imágenes usan {img}. Para igualarlas usa Python {img}.")


# ------------------------------------------------------------------ puertos y direcciones
def container_ports():
    out = {}
    for name, svc in built_services().items():
        text = dockerfile_of(svc)[1].read_text(encoding="utf-8")
        expose = int(re.search(r"^EXPOSE (\d+)", text, re.M).group(1))
        uvicorn = int(re.search(r'"--port", "(\d+)"', text).group(1))
        health = int(re.search(r"localhost:(\d+)", " ".join(svc["healthcheck"]["test"])).group(1))
        assert expose == uvicorn == health, f"{name}: EXPOSE {expose}, uvicorn {uvicorn}, healthcheck {health}"
        for mapping in svc.get("ports", []):
            assert int(mapping.split(":")[1]) == expose, f"{name}: el puerto publicado no apunta al del contenedor"
        out[name] = expose
    return out


def test_puertos_del_dockerfile_uvicorn_healthcheck_y_publicacion_coinciden():
    ports = container_ports()
    assert len(set(ports.values())) == len(ports), f"puertos repetidos: {ports}"


def test_direcciones_internas_apuntan_al_servicio_y_puerto_correctos():
    ports = container_ports()
    ports["mongo"], ports["activemq"] = 27017, 61613
    pattern = re.compile(r"https?://([a-z][\w-]*):(\d+)")
    checked = 0
    # 1) variables de entorno del compose
    for name, svc in COMPOSE["services"].items():
        for key, value in (svc.get("environment") or {}).items():
            for host, port in pattern.findall(str(value)):
                if host == "localhost":
                    continue
                assert host in ports and ports[host] == int(port), f"{name}.{key} = {value}"
                checked += 1
    # 2) valores por defecto escritos en el código
    for d in SERVICES:
        for f in py_files(d):
            for host, port in pattern.findall(f.read_text(encoding="utf-8")):
                if host in ("localhost", "secrets-manager") and host == "localhost":
                    continue
                assert host in ports and ports[host] == int(port), f"{f.relative_to(ROOT)}: http://{host}:{port}"
                checked += 1
    assert checked >= 15


# ------------------------------------------------------------------ secretos y permisos
def _strings(tree):
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def test_cada_servicio_solo_nombra_referencias_que_la_politica_le_permite():
    for d in SERVICES:
        if d == "secrets-manager":
            continue
        sid = SERVICE_ID[d]
        for f in py_files(d):
            for s in _strings(ast.parse(f.read_text(encoding="utf-8"))):
                if s in REFS:
                    assert sid in REFS[s], f"{f.relative_to(ROOT)} usa '{s}' pero policy.json no lo permite a '{sid}'"


def test_cada_tramo_llamador_destino_comparte_su_referencia():
    pares = 0
    for d in SERVICES:
        text = (ROOT / d / "main.py").read_text(encoding="utf-8")
        for aud, body in re.findall(r'make_guard\(\s*"([\w-]+)",\s*(\{.*?\})', text, re.S):
            for caller, ref in ast.literal_eval(body).items():
                assert ref in REFS, f"{d}: referencia inexistente '{ref}'"
                assert aud in REFS[ref] and caller in REFS[ref], f"{d}: el tramo {caller}→{aud} usa '{ref}' que no comparten ambos"
                pares += 1
    gw, gql = load("gw_for_consistency", "gateway/main.py"), load("gql_for_consistency", "graphql-gateway/main.py")
    for _, (_, _, ref, aud) in gw.TARGETS.items():
        assert {"gateway", aud} <= set(REFS[ref]), f"gateway→{aud}: '{ref}'"
        pares += 1
    for _, (_, _, ref, aud) in gql.TARGETS.items():
        assert {"graphql-gateway", aud} <= set(REFS[ref]), f"graphql-gateway→{aud}: '{ref}'"
        pares += 1
    assert pares >= 15


def test_cada_servicio_tiene_su_clave_de_base_de_datos_y_de_broker():
    for d in SERVICES:
        for f in py_files(d):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
                fn = getattr(call.func, "attr", getattr(call.func, "id", ""))
                if fn == "connect" and len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
                    assert SERVICE_ID[d] == call.args[1].value, f"{f.name}: solo '{SERVICE_ID[d]}' puede abrir su propia base"
                    assert SERVICE_ID[d] in REFS[f"db-{call.args[1].value}"]
                if fn == "EventBus" and len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                    user = call.args[1].value
                    assert SERVICE_ID[d] == user and user in REFS[f"mq-{user}"], f"{f.name}: usuario de broker '{user}'"


def test_las_colas_usan_usuarios_con_referencia():
    queues = json.loads((ROOT / "activemq" / "queues.json").read_text(encoding="utf-8"))
    events = load("events_for_consistency", "shared/events.py").EVENTS
    assert {q.removeprefix("/queue/") for q, _ in events.values()} == set(queues), "las colas de events.py y queues.json difieren"
    for q, perms in queues.items():
        for svc in perms["read"] + perms["write"]:
            assert f"mq-{svc}" in REFS, f"{q}: falta mq-{svc}"


# ------------------------------------------------------------------ rutas del gateway
def test_rutas_con_id_unico_y_destino_valido():
    gw = load("gw_routes_consistency", "gateway/main.py")
    sids = [r.sid for r in gw.ROUTES]
    assert all(sids) and len(set(sids)) == len(sids), "ids de servicio vacíos o repetidos"
    pares = [(r.method, r.path) for r in gw.ROUTES]
    assert len(set(pares)) == len(pares), "ruta duplicada"
    for r in gw.ROUTES:
        assert r.target in gw.TARGETS
        assert set(re.findall(r"\{(\w+)\}", r.dest)) <= set(re.findall(r"\{(\w+)\}", r.path)), f"{r.sid}: parámetro del destino ausente en la ruta"
        assert r.method in ("GET", "POST", "PUT", "PATCH", "DELETE")


def _call_text(src, start):
    """Texto de la llamada api(...) desde `start`, respetando paréntesis y comillas."""
    depth, i, quote = 0, start, None
    while i < len(src):
        c = src[i]
        if quote:
            if c == quote and src[i - 1] != "\\":
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:]


def test_cada_llamada_del_frontend_existe_en_el_gateway():
    gw = load("gw_front_consistency", "gateway/main.py")
    rutas = {(r.method, r.path) for r in gw.ROUTES} | {("POST", "/auth/login"), ("POST", "/auth/logout"), ("GET", "/auth/session")}
    llamadas = 0
    for f in list((ROOT / "frontend").rglob("*.js")) + list((ROOT / "frontend").rglob("*.php")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\bapi\(\s*'(/[^'?]*)", src):
            prefijo, texto = m.group(1), _call_text(src, m.start() + 3)
            met = re.search(r"method:\s*'(\w+)'", texto)
            metodo = met.group(1) if met else "GET"
            dinamica = prefijo.endswith("/")
            ok = any(mt == metodo and (p.startswith(prefijo) if dinamica else p == prefijo) for mt, p in rutas)
            assert ok, f"{f.relative_to(ROOT)}: api('{prefijo}…') con {metodo} no existe en gateway/routes.py"
            llamadas += 1
    assert llamadas >= 8


# ------------------------------------------------------------------ docker-compose y Dockerfiles
def test_compose_archivos_de_entorno_y_montajes_los_genera_gen_secrets(tmp_path):
    gen_secrets.generate(out=tmp_path / "secrets", policy_path=ROOT / "secrets-manager" / "policy.json")
    faltan = []
    for name, svc in COMPOSE["services"].items():
        env_files = svc.get("env_file", [])
        for ef in [env_files] if isinstance(env_files, str) else env_files:
            if not (tmp_path / ef.removeprefix("./")).exists():
                faltan.append(f"{name}: {ef}")
        for vol in svc.get("volumes", []):
            src = vol.split(":")[0]
            if src.startswith("./secrets"):
                if not (tmp_path / src.removeprefix("./")).exists():
                    faltan.append(f"{name}: {src}")
    for sec in COMPOSE.get("secrets", {}).values():
        if not (tmp_path / sec["file"].removeprefix("./")).exists():
            faltan.append(f"secreto {sec['file']}")
    assert not faltan, f"gen_secrets.py no genera: {faltan}"


def test_compose_dependencias_existen_tienen_salud_y_no_hay_ciclos():
    svcs = COMPOSE["services"]
    grafo = {}
    for name, svc in svcs.items():
        deps = list((svc.get("depends_on") or {}))
        for d in deps:
            assert d in svcs, f"{name} depende de '{d}', que no existe"
            assert "healthcheck" in svcs[d], f"{name} espera la salud de '{d}', que no tiene healthcheck"
            assert svc["depends_on"][d]["condition"] == "service_healthy"
        grafo[name] = deps
    visitando, hecho = set(), set()

    def visita(n):
        assert n not in visitando, f"ciclo de dependencias en {n}"
        if n in hecho:
            return
        visitando.add(n)
        for d in grafo[n]:
            visita(d)
        visitando.discard(n); hecho.add(n)
    for n in grafo:
        visita(n)


def test_solo_gateway_y_proveedor_publican_puertos_y_lo_privado_esta_aislado():
    assert COMPOSE["networks"]["private"].get("internal") is True
    publicados = {n for n, s in COMPOSE["services"].items() if s.get("ports")}
    assert publicados == {"gateway", "provider-sim"}
    for n, s in COMPOSE["services"].items():
        redes = set(s.get("networks", []))
        if n == "gateway":
            assert redes == {"public", "private"}
        elif n == "provider-sim":
            assert redes == {"public"}, "el proveedor simulado es un tercero: no debe alcanzar la red privada"
        else:
            assert redes == {"private"}, f"{n} debe estar solo en la red privada"


def test_contenedores_python_endurecidos():
    for n, s in built_services().items():
        assert s.get("read_only") is True and s.get("cap_drop") == ["ALL"] and "no-new-privileges:true" in s.get("security_opt", []), n
        assert "USER app" in dockerfile_of(s)[1].read_text(encoding="utf-8"), f"{n}: el contenedor no debe correr como root"


def test_dockerfiles_copian_todo_lo_que_el_servicio_necesita():
    for name, svc in built_services().items():
        ctx, dockerfile = dockerfile_of(svc)
        fuentes = set()
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            if line.startswith("COPY "):
                partes = line.split()[1:-1]
                fuentes |= {p.rstrip("/") for p in partes}
                for p in partes:
                    assert (ctx / p).exists(), f"{name}: COPY {p} no existe respecto de {ctx}"
        carpeta = ROOT / next(d for d in SERVICES if SERVICE_ID[d] == name.removeprefix("svc-") or d == name)
        for f in carpeta.iterdir():
            if f.is_file() and not f.name.startswith(".") and f.name != "Dockerfile" and f.suffix != ".pyc":
                assert any(s.endswith(f.name) for s in fuentes), f"{name}: {f.name} existe en la carpeta pero el Dockerfile no lo copia"
        importa_shared = any("from shared" in p.read_text(encoding="utf-8") for p in py_files(carpeta.name))
        assert (not importa_shared) or any(s.startswith("shared") for s in fuentes), f"{name}: importa 'shared' pero no lo copia"


def test_variables_del_compose_estan_documentadas_en_env_example():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    usadas = set(re.findall(r"\$\{(\w+)", compose_text))
    documentadas = set(re.findall(r"^(\w+)=", (ROOT / ".env.example").read_text(encoding="utf-8"), re.M))
    assert usadas, "el compose no usa variables"
    assert usadas <= documentadas, f"faltan en .env.example: {usadas - documentadas}"
    assert not (documentadas - usadas), f"sobran en .env.example (el compose no las usa): {documentadas - usadas}"
