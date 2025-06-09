from pydantic import BaseModel
from typing import List

class ProductoInsumoItem(BaseModel):
    insumo_id: int
    cantidad: float

class ProductoInsumoCreate(BaseModel):
    producto_id: int
    insumos: List[ProductoInsumoItem]

class ProductoInsumoOut(BaseModel):
    id: int
    producto_id: int
    insumo_id: int
    cantidad: float

    class Config:
        orm_mode = True
