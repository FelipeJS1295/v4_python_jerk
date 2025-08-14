from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime
from enum import Enum
from typing import List

# Enums para liquidaciones
class TipoLiquidacion(str, Enum):
    venta = "venta"
    devolucion = "devolucion"
    cancelacion = "cancelacion"

class EstadoLiquidacion(str, Enum):
    pendiente = "pendiente"
    procesada = "procesada"
    cerrada = "cerrada"

class EstadoPago(str, Enum):
    pendiente = "pendiente"
    pagada = "pagada"
    fallida = "fallida"
    reembolsada = "reembolsada"

class VentaBase(BaseModel):
    cliente_id: int
    numero_orden: Optional[str] = None
    cliente_final: Optional[str] = None
    rut_documento: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    fecha_entrega: Optional[date] = None
    fecha_cliente: Optional[date] = None
    fecha_compra: Optional[date] = None
    producto: Optional[str] = None
    precio: Optional[float] = None
    precio_cliente: Optional[float] = None
    costo_despacho: Optional[float] = None
    comuna: Optional[str] = None
    direccion: Optional[str] = None
    region: Optional[str] = None
    sku: Optional[str] = None
    estado: Optional[str] = None
    documento: Optional[str] = None
    razon_social: Optional[str] = None
    rut: Optional[str] = None
    giro: Optional[str] = None
    direccion_factura: Optional[str] = None
    courier: Optional[str] = None
    unidades: Optional[int] = None
    users_id: Optional[int] = None
    
    # NUEVOS CAMPOS PARA LIQUIDACIONES
    tipo_liquidacion: Optional[TipoLiquidacion] = None
    monto_pago_liquidacion: Optional[float] = None
    fecha_liquidacion: Optional[datetime] = None
    numero_liquidacion: Optional[str] = None
    estado_liquidacion: Optional[EstadoLiquidacion] = EstadoLiquidacion.pendiente
    archivo_liquidacion: Optional[str] = None
    fecha_procesamiento_liquidacion: Optional[datetime] = None

class VentaCreate(VentaBase):
    pass

class VentaUpdate(BaseModel):
    """Schema para actualizar datos de liquidación"""
    tipo_liquidacion: Optional[TipoLiquidacion] = None
    monto_pago_liquidacion: Optional[float] = None
    fecha_liquidacion: Optional[datetime] = None
    numero_liquidacion: Optional[str] = None
    estado_liquidacion: Optional[EstadoLiquidacion] = None
    archivo_liquidacion: Optional[str] = None

class VentaOut(BaseModel):
    id: int
    numero_orden: str
    fecha_entrega: str
    producto: str
    estado: str
    sku: Optional[str] = None

class VentaDetalle(BaseModel):
    """Schema completo para mostrar detalles de venta con liquidación"""
    id: int
    cliente_id: int
    numero_orden: str
    cliente_final: str
    producto: str
    precio: Optional[float] = None
    precio_cliente: Optional[float] = None
    sku: str
    estado: str
    fecha_compra: Optional[date] = None
    fecha_entrega: Optional[date] = None
    
    # Información de liquidación
    tipo_liquidacion: Optional[TipoLiquidacion] = None
    monto_pago_liquidacion: Optional[float] = None
    fecha_liquidacion: Optional[datetime] = None
    numero_liquidacion: Optional[str] = None
    estado_liquidacion: EstadoLiquidacion = EstadoLiquidacion.pendiente
    archivo_liquidacion: Optional[str] = None
    fecha_procesamiento_liquidacion: Optional[datetime] = None
    
    # Campos calculados
    diferencia_precio: Optional[float] = None
    esta_liquidada: bool = False
    
    class Config:
        from_attributes = True

class ProductoVentaManual(BaseModel):
    """Schema para productos en carga manual"""
    producto: str
    cantidad: int
    fecha_entrega: date

class VentaManualRequest(BaseModel):
    """Schema para request de venta manual"""
    cliente_id: int
    numero_orden: str
    fecha_compra: date
    productos: List[ProductoVentaManual]

class VentaManualResponse(BaseModel):
    """Schema para response de venta manual"""
    mensaje: str
    ventas_creadas: int