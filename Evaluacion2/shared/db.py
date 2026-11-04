"""Conexión a MongoDB con el usuario propio del servicio (permisos solo sobre <servicio>_db)."""
import os


def connect(provider, service: str, url: str | None = None):
    from pymongo import MongoClient
    password = provider.get(f"db-{service}")["current"]
    client = MongoClient(url or os.environ["MONGO_URL"], username=service, password=password,
                         authSource=f"{service}_db", serverSelectionTimeoutMS=3000)
    return client[f"{service}_db"]
