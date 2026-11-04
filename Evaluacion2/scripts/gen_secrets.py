"""Genera secretos locales (NO versionar la carpeta secrets/).
Uso:  python scripts/gen_secrets.py [--force]"""
import hashlib, json, os, pathlib, secrets, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "secrets-manager" / "policy.json"
OUT = ROOT / "secrets"
MANAGER_URL = os.environ.get("SECRETS_MANAGER_URL", "http://secrets-manager:8200")


def generate(out=OUT, policy_path=POLICY, force=False):
    out = pathlib.Path(out)
    if (out / "store.json").exists() and not force:
        raise SystemExit("Ya existen secretos. Usa --force para regenerarlos (invalida todo lo anterior).")
    policy = json.loads(pathlib.Path(policy_path).read_text())
    refs = list(policy["refs"])
    services = sorted({s for c in policy["refs"].values() for s in c} | set(policy["rotators"]))

    store = {r: {"current": secrets.token_urlsafe(32), "previous": None, "rotated_at": 0} for r in refs}
    keys = {s: secrets.token_urlsafe(32) for s in services}
    hashes = {s: hashlib.sha256(k.encode()).hexdigest() for s, k in keys.items()}

    (out / "env").mkdir(parents=True, exist_ok=True)
    (out / "store.json").write_text(json.dumps(store, indent=2))
    (out / "service_key_hashes.json").write_text(json.dumps(hashes, indent=2))
    (out / "service_keys.json").write_text(json.dumps(keys, indent=2))
    for s, k in keys.items():
        (out / "env" / f"{s}.env").write_text(f"SERVICE_ID={s}\nSERVICE_KEY={k}\nSECRETS_MANAGER_URL={MANAGER_URL}\n")
    for f in out.rglob("*"):
        if f.is_file():
            try: os.chmod(f, 0o600)
            except OSError: pass
    return refs, services


if __name__ == "__main__":
    refs, services = generate(force="--force" in sys.argv)
    print(f"Generadas {len(refs)} referencias y {len(services)} credenciales de servicio en {OUT}")
