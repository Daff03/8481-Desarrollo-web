"""Genera secretos locales (NO versionar la carpeta secrets/).
Uso:  python scripts/gen_secrets.py [--force]

secrets/
  manager/            lo único que ve el secrets-manager: store.json y service_key_hashes.json
  env/<servicio>.env  SERVICE_ID, SERVICE_KEY y URL del gestor para cada servicio
  mongo-init/init.js  crea un usuario de MongoDB por servicio (usa las mismas claves db-* del gestor)
  mongo_root_password contraseña root de MongoDB (secreto de Docker, solo la lee el contenedor mongo)
  activemq/           activemq.xml con los usuarios y permisos del broker
  seed.env            contraseñas de admin@alsahara.cl y cajero@alsahara.cl
  service_keys.json   claves en claro de cada servicio, solo para pruebas y admin-cli
Los archivos montados dentro de contenedores (manager/, mongo-init/, activemq/, mongo_root_password) quedan en 644 y el resto en 600."""
import hashlib, json, os, pathlib, secrets, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "secrets-manager" / "policy.json"
OUT = ROOT / "secrets"
MANAGER_URL = os.environ.get("SECRETS_MANAGER_URL", "http://secrets-manager:8200")


QUEUES = ROOT / "activemq" / "queues.json"


def _write(path, text):
    """Siempre UTF-8 y saltos de línea \\n, sin importar el sistema: en Windows Python usa cp1252 y \\r\\n por defecto, y eso
    deja un activemq.xml que declara UTF-8 pero no lo es (el broker no arranca) y archivos .env con \\r al final de cada valor."""
    pathlib.Path(path).write_text(text, encoding="utf-8", newline="\n")


XML_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Generado por scripts/gen_secrets.py. No versionar: contiene credenciales. -->
<beans xmlns="http://www.springframework.org/schema/beans"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="http://www.springframework.org/schema/beans http://www.springframework.org/schema/beans/spring-beans.xsd
                           http://activemq.apache.org/schema/core http://activemq.apache.org/schema/core/activemq-core.xsd">
  <broker xmlns="http://activemq.apache.org/schema/core" brokerName="alsahara" dataDirectory="/opt/apache-activemq/data" useJmx="false" persistent="true">
    <destinationPolicy><policyMap><policyEntries>
      <!-- Un DLQ por cola: los mensajes rechazados (nack) quedan en DLQ.<cola> para revisarlos -->
      <policyEntry queue="&gt;"><deadLetterStrategy><individualDeadLetterStrategy queuePrefix="DLQ." useQueueForQueueMessages="true"/></deadLetterStrategy></policyEntry>
    </policyEntries></policyMap></destinationPolicy>
    <persistenceAdapter><kahaDB directory="/opt/apache-activemq/data/kahadb"/></persistenceAdapter>
    <!-- Limites modestos: por defecto el broker reserva hasta 50 GB de disco y no arranca bien en equipos con poco espacio -->
    <systemUsage><systemUsage>
      <memoryUsage><memoryUsage percentOfJvmHeap="70"/></memoryUsage>
      <storeUsage><storeUsage limit="1 gb"/></storeUsage>
      <tempUsage><tempUsage limit="512 mb"/></tempUsage>
    </systemUsage></systemUsage>
    <plugins>
      <simpleAuthenticationPlugin anonymousAccessAllowed="false"><users>
"""


def activemq_xml(store, refs, queues_path):
    """Un usuario del broker por servicio (clave = referencia mq-<servicio>) y permisos de lectura/escritura por cola.
    Sin consola web: no se importa jetty.xml."""
    from xml.sax.saxutils import quoteattr
    queues = json.loads(pathlib.Path(queues_path).read_text(encoding="utf-8"))
    users = [r[3:] for r in refs if r.startswith("mq-")]
    for q, p in queues.items():
        for svc in p["read"] + p["write"]:
            if svc not in users:
                raise SystemExit(f"La cola {q} usa '{svc}', que no tiene referencia mq-{svc} en policy.json")
    xml = XML_HEAD
    for u in users:
        xml += f'        <authenticationUser username={quoteattr(u)} password={quoteattr(store["mq-" + u]["current"])} groups={quoteattr(u)}/>\n'
    xml += "      </users></simpleAuthenticationPlugin>\n      <authorizationPlugin><map><authorizationMap><authorizationEntries>\n"
    for q, p in queues.items():
        xml += (f'        <authorizationEntry queue={quoteattr(q)} read={quoteattr(",".join(p["read"]))} '
                f'write={quoteattr(",".join(p["write"]))} admin={quoteattr(",".join(sorted(set(p["read"] + p["write"]))))}/>\n')
    xml += f'        <authorizationEntry topic="ActiveMQ.Advisory.&gt;" read={quoteattr(",".join(users))} write={quoteattr(",".join(users))} admin={quoteattr(",".join(users))}/>\n'
    xml += ('      </authorizationEntries></authorizationMap></map></authorizationPlugin>\n    </plugins>\n'
            '    <transportConnectors><transportConnector name="stomp" uri="stomp://0.0.0.0:61613?maximumConnections=100&amp;wireFormat.maxDataLength=1048576"/></transportConnectors>\n'
            '  </broker>\n</beans>\n')
    return xml


def generate(out=OUT, policy_path=POLICY, force=False):
    out = pathlib.Path(out)
    if (out / "manager" / "store.json").exists() and not force:
        raise SystemExit("Ya existen secretos. Usa --force para regenerarlos (invalida todo lo anterior).")
    policy = json.loads(pathlib.Path(policy_path).read_text(encoding="utf-8"))
    refs = list(policy["refs"])
    services = sorted({s for c in policy["refs"].values() for s in c} | set(policy["rotators"]))

    store = {r: {"current": secrets.token_urlsafe(32), "previous": None, "rotated_at": 0} for r in refs}
    keys = {s: secrets.token_urlsafe(32) for s in services}
    hashes = {s: hashlib.sha256(k.encode()).hexdigest() for s, k in keys.items()}

    for d in ("manager", "env", "mongo-init"):
        (out / d).mkdir(parents=True, exist_ok=True)
    _write(out / "manager" / "store.json", json.dumps(store, indent=2))
    _write(out / "manager" / "service_key_hashes.json", json.dumps(hashes, indent=2))
    _write(out / "service_keys.json", json.dumps(keys, indent=2))
    _write(out / "mongo_root_password", secrets.token_urlsafe(32))
    # Contraseñas de la demo para admin@alsahara.cl y cajero@alsahara.cl (las lee auth al sembrar; consúltalas en este archivo).
    _write(out / "seed.env", f"SEED_ADMIN_PASSWORD={secrets.token_urlsafe(12)}\nSEED_CAJERO_PASSWORD={secrets.token_urlsafe(12)}\n")
    for s, k in keys.items():
        # El proveedor de pagos simulado es una entidad externa: recibe su secreto de webhook por entorno, no del gestor.
        extra = f"WEBHOOK_SECRET={store['prov-webhook']['current']}\n" if s == "provider-sim" else ""
        _write(out / "env" / f"{s}.env", f"SERVICE_ID={s}\nSERVICE_KEY={k}\nSECRETS_MANAGER_URL={MANAGER_URL}\n{extra}")

    # Un usuario de MongoDB por servicio, con permisos solo sobre su base (<servicio>_db).
    lines = ["// Generado por scripts/gen_secrets.py. No versionar."]
    for ref in refs:
        if ref.startswith("db-"):
            svc = ref[3:]
            lines.append(f'db.getSiblingDB("{svc}_db").createUser({{user: "{svc}", pwd: {json.dumps(store[ref]["current"])}, '
                         f'roles: [{{role: "readWrite", db: "{svc}_db"}}]}});')
    _write(out / "mongo-init" / "init.js", "\n".join(lines) + "\n")

    (out / "activemq").mkdir(exist_ok=True)
    _write(out / "activemq" / "activemq.xml", activemq_xml(store, refs, QUEUES))

    # Los archivos que un contenedor lee por bind-mount deben ser legibles por el usuario del contenedor (en Linux/macOS el uid
    # del contenedor no es el del anfitrión); el resto queda en 600. La carpeta secrets/ es local y no se versiona.
    for f in out.rglob("*"):
        if f.is_file():
            shared = f.parent.name in BIND_MOUNTED or f.name == "mongo_root_password"
            try: os.chmod(f, 0o644 if shared else 0o600)
            except OSError: pass
    return refs, services


BIND_MOUNTED = {"manager", "mongo-init", "activemq"}


if __name__ == "__main__":
    refs, services = generate(force="--force" in sys.argv)
    mail = ROOT / "mail-outbox"   # donde el notifier deja los correos de prueba; se crea aquí para que no lo cree Docker como root
    mail.mkdir(exist_ok=True)
    try: os.chmod(mail, 0o777)
    except OSError: pass
    print(f"Generadas {len(refs)} referencias y {len(services)} credenciales de servicio en {OUT}")
    print("Contraseñas de admin@alsahara.cl y cajero@alsahara.cl: ver secrets/seed.env")
