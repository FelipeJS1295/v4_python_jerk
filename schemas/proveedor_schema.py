from pydantic import BaseModel
from typing import Optional

class ProveedorBase(BaseModel):
    rut: str
    nombre: str
    direccion: Optional[str] = None
    contacto: Optional[str] = None
    forma_pago: Optional[str] = None

class ProveedorCreate(ProveedorBase):
    pass

class ProveedorOut(ProveedorBase):
    id: int

    class Config:
        orm_mode = True
