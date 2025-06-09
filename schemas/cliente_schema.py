from pydantic import BaseModel
from typing import Optional

class ClienteBase(BaseModel):
    nombre: str
    rut: str
    direccion: Optional[str] = None
    contacto: Optional[str] = None
    dias_pago: Optional[int] = None
    porcentaje_comision: Optional[float] = None
    cobro_logistico: Optional[float] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteOut(ClienteBase):
    id: int

    class Config:
        orm_mode = True