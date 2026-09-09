#pip install fastapi motor pymongo
#pip install fastapi "uvicorn[standard]" motor pydantic
#Para inicar el sv
#uvicorn main:app  

from typing import List, Optional, Dict
from itertools import count

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from contextlib import asynccontextmanager

#configuracion de MongoDB
MONGO_URI = "mongodb://localhost:27017"  
DB_NAME = "Al-Sahara"
COOL_NAME = "items"

client: AsyncIOMotorClient | None = None
db = None
coll = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db, coll
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    coll = db[COOL_NAME]
    yield
    client.close()

app = FastAPI(title="FastApi", lifespan=lifespan)

class Item(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre del producto")
    precio: float = Field(gt=0, description="Precio del producto > 0")
    tags: List[str] = Field(default_factory=List)
    activo: bool = True

class ItemIN(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre del producto")
    precio: float = Field(gt=0, description="Precio del producto > 0")
    tags: List[str] = Field(default_factory=List)
    activo: bool = True

class ItemOUT(Item):
    id: str 

def doc_to_itemout(doc: Dict) -> ItemOUT:
    return ItemOUT(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        precio=doc["precio"],
        tags=doc.get("tags", []),
        activo=doc.get("activo", True)
    )

#endpoints

@app.get("/health", tags=["sistema"])
def health_check():
    return {"status": "ok"}

@app.get("/items", response_model=List[ItemOUT], tags=["items"])
async def listar_items(
    q: Optional[str] = Query(None, description="Filtro de búsqueda por nombre"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = {}
    if q:
        query["nombre"] = {"$regex": q, "$options": "i"}  # Búsqueda insensible a mayúsculas/minúsculas

    cursor = coll.find(query).skip(skip).limit(limit)
    items: List[ItemOUT] = []
    async for doc in cursor:
        items.append(doc_to_itemout(doc))
    return items

@app.post("/items", response_model=ItemOUT, status_code=201, tags=["items"])
async def crear_item(item: ItemIN):
    res = await coll.insert_one(item.model_dump())
    doc = await coll.find_one({"_id": res.inserted_id})
    return doc_to_itemout(doc)

@app.get("/items/{item_id}", response_model=ItemOUT, status_code=201, tags=["items"])
async def obtener_item(item_id: str):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await coll.find_one({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return doc_to_itemout(doc)

@app.put("/items/{item_id}", response_model=ItemOUT, status_code=200, tags=["items"])
async def actualizar_item(item_id: str, item: ItemIN):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    res = await coll.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": item.model_dump()}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    doc = await coll.find_one({"_id": ObjectId(item_id)})
    return doc_to_itemout(doc)

@app.delete("/items/{item_id}", status_code=204, tags=["items"])
async def eliminar_item(item_id: str):  
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    res = await coll.delete_one({"_id": ObjectId(item_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return None

