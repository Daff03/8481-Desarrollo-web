"""Datos de prueba ficticios: los 12 platos del menú y dos promociones. Idempotente (upsert por slug).
Uso dentro del contenedor:  python seed.py   (requiere MONGO_URL y credenciales del servicio)"""
from datetime import datetime, timezone

IMG = "assets/img/platos/"
PLATOS = [  # slug, nombre, categoría, precio CLP, descripción, popular
    ("hummus-tradicional", "Hummus Tradicional", "entradas", 6990, "Puré de garbanzos con tahini, aceite de oliva y especias árabes, servido con pan pita tibio.", True),
    ("baba-ganoush", "Baba Ganoush", "entradas", 7490, "Berenjena ahumada al fuego, mezclada con ajo, limón y tahini.", True),
    ("fatayer-espinaca", "Fatayer de Espinaca", "entradas", 5990, "Empanadillas árabes horneadas, rellenas de espinaca, cebolla y especias.", False),
    ("shawarma-cordero", "Shawarma de Cordero", "carnes", 12990, "Cordero marinado 24 horas en especias árabes, servido con arroz y salsa de ajo.", True),
    ("kebab-mixto", "Kebab Mixto", "carnes", 13990, "Brochetas de cordero y pollo a la parrilla, acompañadas de arroz árabe.", False),
    ("kafta-al-sahara", "Kafta Al Sahara", "carnes", 11990, "Carne molida especiada a la parrilla, bañada en salsa de tahini.", False),
    ("falafel-casero", "Falafel Casero", "vegetarianos", 8990, "Croquetas de garbanzo y hierbas frescas, fritas al momento, con salsa de yogur.", True),
    ("tabbouleh", "Tabbouleh", "vegetarianos", 6490, "Ensalada de perejil fresco, trigo bulgur, tomate y limón.", False),
    ("fatteh-garbanzos", "Fatteh de Garbanzos", "vegetarianos", 8490, "Pan pita crocante con garbanzos, yogur y un toque de granada.", False),
    ("baklava", "Baklava", "postres", 4990, "Hojaldre crujiente relleno de nueces, bañado en miel de rosas.", True),
    ("kunafa", "Kunafa", "postres", 5990, "Queso dulce cubierto con fideos crujientes, bañado en almíbar.", False),
    ("muhallabia", "Muhallabia", "postres", 4490, "Pudín de leche con agua de rosas, decorado con pistachos.", False),
]


def seed(db, stock=50):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for slug, nombre, cat, precio, desc, popular in PLATOS:
        db.products.update_one(
            {"slug": slug},
            {"$setOnInsert": {"stock": stock, "disponible": True, "activo": True, "created_at": now},
             "$set": {"nombre": nombre, "categoria": cat, "precio": precio, "descripcion": desc, "popular": popular,
                      "imagen": f"{IMG}{slug}.jpg", "updated_at": now}},
            upsert=True)
    postres = [p["_id"] for p in db.products.find({"categoria": "postres"}, {"_id": 1})]
    db.promotions.update_one(
        {"titulo": "Martes de postres"},
        {"$set": {"descuentoPct": 15, "vigenciaDesde": "2026-11-01", "vigenciaHasta": "2026-12-31", "productIds": postres}},
        upsert=True)
    return db.products.count_documents({})


if __name__ == "__main__":
    import sys
    from shared import db as dbmod
    from shared.secret_provider import SecretProvider
    print(f"Productos en inventory_db: {seed(dbmod.connect(SecretProvider(), 'inventory'))}", file=sys.stdout)
