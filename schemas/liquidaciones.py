from pydantic import BaseModel, validator
from typing import Optional, List, Literal
from datetime import datetime, date
from enum import Enum

# Enums
class RetailEnum(str, Enum):
    falabella = "falabella"
    cencosud = "cencosud"
    walmart = "walmart"
    ripley = "ripley"
    hites = "hites"

class EstadoLiquidacion(str, Enum):
    pendiente = "pendiente"
    procesada = "procesada"
    cerrada = "cerrada"
    error = "error"

class TipoTransaccion(str, Enum):
    venta = "venta"
    devolucion = "devolucion"
    cancelacion = "cancelacion"

# Schemas para el procesamiento de liquidaciones
class LiquidacionCargar(BaseModel):
    """Schema para cargar un archivo de liquidación"""
    retail: RetailEnum
    numero_liquidacion: Optional[str] = None
    
    @validator('retail')
    def validar_retail(cls, v):
        if v not in RetailEnum.__members__.values():
            raise ValueError(f'Retail debe ser uno de: {", ".join(RetailEnum.__members__.keys())}')
        return v

class ResultadoProcesamientoLiquidacion(BaseModel):
    """Schema para el resultado del procesamiento"""
    success: bool
    message: str
    retail: str
    archivo: str
    numero_liquidacion: Optional[str] = None
    
    # Estadísticas del procesamiento
    ordenes_procesadas: int = 0
    ordenes_actualizadas: int = 0
    ordenes_no_encontradas: int = 0
    ordenes_con_error: int = 0
    
    # Montos
    monto_total: float = 0
    monto_ventas: float = 0
    monto_devoluciones: float = 0
    
    # Detalles
    fecha_liquidacion: Optional[datetime] = None
    fecha_procesamiento: Optional[datetime] = None
    errores: List[str] = []

class LiquidacionResumen(BaseModel):
    """Schema para mostrar resumen de liquidación"""
    id: Optional[int] = None
    retail: str
    numero_liquidacion: str
    fecha_liquidacion: datetime
    monto_total: float
    cantidad_ordenes: int
    cantidad_ventas: int
    cantidad_devoluciones: int
    estado: EstadoLiquidacion
    archivo_original: str
    fecha_procesamiento: datetime

class OrdenEstado(BaseModel):
    """Schema para mostrar estado de una orden"""
    numero_orden: str
    retail: str
    fecha_orden: date
    monto: float
    estado_pago: str
    fecha_pago: Optional[datetime] = None
    numero_liquidacion: Optional[str] = None
    tipo_liquidacion: Optional[TipoTransaccion] = None
    monto_pago_liquidacion: Optional[float] = None
    
    # Información del producto
    sku: Optional[str] = None
    producto: Optional[str] = None
    cliente_final: Optional[str] = None

class OrdenDetalle(OrdenEstado):
    """Schema extendido con más detalles de la orden"""
    id: int
    cliente_id: int
    precio_original: Optional[float] = None
    precio_cliente: Optional[float] = None
    diferencia_precio: Optional[float] = None
    
    # Información de entrega
    direccion: Optional[str] = None
    comuna: Optional[str] = None
    region: Optional[str] = None
    courier: Optional[str] = None
    fecha_entrega: Optional[date] = None
    
    # Información de liquidación
    archivo_liquidacion: Optional[str] = None
    fecha_procesamiento_liquidacion: Optional[datetime] = None

class FiltrosOrdenes(BaseModel):
    """Schema para filtros de búsqueda de órdenes"""
    retail: Optional[RetailEnum] = None
    numero_orden: Optional[str] = None
    estado_pago: Optional[str] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    numero_liquidacion: Optional[str] = None
    tipo_liquidacion: Optional[TipoTransaccion] = None
    page: int = 1
    limit: int = 10

class EstadisticasLiquidaciones(BaseModel):
    """Schema para estadísticas generales"""
    total_liquidaciones: int = 0
    monto_total_liquidado: float = 0
    ordenes_pagadas: int = 0
    ordenes_pendientes: int = 0
    
    # Por retail
    estadisticas_por_retail: dict = {}
    
    # Por período
    ultimo_mes: dict = {}
    
class ConfiguracionRetail(BaseModel):
    """Schema para configuración específica de cada retail"""
    retail: RetailEnum
    cliente_id: int
    nombre_completo: str
    formato_archivo: str
    columnas_mapeo: dict
    validaciones_especiales: List[str] = []

# Schema para respuestas de API
class RespuestaAPI(BaseModel):
    """Schema base para respuestas de API"""
    success: bool
    message: str
    data: Optional[dict] = None
    errors: List[str] = []

class ListaPaginada(BaseModel):
    """Schema para listas paginadas"""
    items: List[dict] = []
    total: int = 0
    page: int = 1
    limit: int = 10
    total_pages: int = 0