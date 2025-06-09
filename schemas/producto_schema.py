from pydantic import BaseModel
from typing import Optional

class ProductoBase(BaseModel):
    sku: str
    sku_esqueleto: Optional[str] = None
    sku_hites: Optional[str] = None
    sku_la_polar: Optional[str] = None
    nombre: str
    esqueleto: Optional[str] = None
    imagen_corte: Optional[str] = None
    imagen_tapizado: Optional[str] = None
    imagen_corte_esqueleto: Optional[str] = None
    imagen_esqueleto: Optional[str] = None
    costo_costura: Optional[float] = None
    costo_tapiceria: Optional[float] = None
    costo_armado: Optional[float] = None
    costo_corte: Optional[float] = None
    costo_esqueleteria: Optional[float] = None
    users_id: Optional[int] = None
    precio_venta: Optional[float] = None
    tipo_producto: Optional[str] = None
    descripcion_producto: Optional[str] = None
    producto_imagenes_venta_id: Optional[int] = None
    img_1: Optional[str] = None
    img_2: Optional[str] = None
    img_3: Optional[str] = None
    img_4: Optional[str] = None
    img_5: Optional[str] = None
    img_6: Optional[str] = None
    img_7: Optional[str] = None
    img_8: Optional[str] = None
    img_9: Optional[str] = None
    img_10: Optional[str] = None
    precio_descuento: Optional[float] = None
    tipo_producto_venta: Optional[str] = None
    visitas: Optional[int] = None
    dimensiones: Optional[str] = None
    material: Optional[str] = None
    colores_disponibles: Optional[str] = None
    tiempo_entrega: Optional[str] = None
    colores_hex: Optional[str] = None

class ProductoCreate(ProductoBase):
    pass

class ProductoOut(ProductoBase):
    id: int

    class Config:
        orm_mode = True
