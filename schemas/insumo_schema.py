from pydantic import BaseModel
from typing import Optional

class InsumoBase(BaseModel):
    sku_padre: str
    sku_hijo: Optional[str] = None
    nombre: str
    unidad_medida: str
    proveedor_id: int
    precio_costo: Optional[float] = None
    precio_venta: Optional[float] = None

class InsumoCreate(InsumoBase):
    pass

class InsumoOut(InsumoBase):
    id: int

    class Config:
        orm_mode = True
