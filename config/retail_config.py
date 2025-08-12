from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import os
from typing import Optional
import pandas as pd
from datetime import datetime
import json
import mysql.connector
from io import BytesIO

# Imports de esquemas
from schemas.liquidaciones import (
    LiquidacionCargar, 
    ResultadoProcesamientoLiquidacion,
    OrdenEstado,
    FiltrosOrdenes,
    EstadisticasLiquidaciones,
    RespuestaAPI
)
from schemas.venta_schema import VentaUpdate, TipoLiquidacion, EstadoLiquidacion

# Configuración del router
router = APIRouter(prefix="/liquidaciones", tags=["liquidaciones"])
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "..", "templates"))

# Configuración de retailers (basada en tu tabla clientes)
RETAIL_CONFIG = {
    "falabella": {
        "cliente_id": 1, 
        "nombre": "Falabella Retail S.A.",
        "hoja_excel": "Hoja1"
    },
    "cencosud": {
        "cliente_id": 2, 
        "nombre": "CENCOSUD RETAIL S.A.",
        "hoja_excel": "transacciones",
        "columnas": {
            "numero_orden": "número orden",
            "tipo": "tipo",
            "monto": "monto a pagar", 
            "fecha_liquidacion": "fecha liq.factura",
            "numero_liquidacion": "número liq.factura"
        }
    },
    "walmart": {
        "cliente_id": 3, 
        "nombre": "WALMART CHILE S.A.",
        "hoja_excel": "Hoja1"
    },
    "hites": {
        "cliente_id": 5, 
        "nombre": "Hites S.A.",
        "hoja_excel": "Hoja1"
    }
}

# ===== RUTAS DE VISTAS =====

@router.get("/")
async def lista_liquidaciones(request: Request):
    """Vista principal - Lista de liquidaciones"""
    return templates.TemplateResponse("liquidaciones/lista.html", {
        "request": request
    })

@router.get("/cargar")
async def cargar_liquidacion(request: Request):
    """Vista para cargar nueva liquidación"""
    return templates.TemplateResponse("liquidaciones/cargar.html", {
        "request": request
    })

@router.get("/ordenes")
async def estado_ordenes(request: Request):
    """Vista del estado de órdenes"""
    return templates.TemplateResponse("liquidaciones/ordenes.html", {
        "request": request
    })

# ===== RUTAS DE API =====

@router.get("/api/liquidaciones")
async def obtener_liquidaciones(
    page: int = 1,
    limit: int = 10,
    retail: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
):
    """Obtener lista de liquidaciones con filtros"""
    try:
        # TODO: Conectar con la base de datos
        # Por ahora retornamos datos de ejemplo
        liquidaciones = [
            {
                "id": 1,
                "retail": "Falabella",
                "numero_liquidacion": "LIQ-FAL-2024-001",
                "fecha_liquidacion": "2024-08-10",
                "monto_total": 2450000,
                "cantidad_ordenes": 45,
                "estado": "Procesada",
                "archivo_original": "falabella_liquidacion_agosto.xlsx"
            },
            {
                "id": 2,
                "retail": "Cencosud",
                "numero_liquidacion": "LIQ-CEN-2024-002",
                "fecha_liquidacion": "2024-08-09",
                "monto_total": 1890000,
                "cantidad_ordenes": 32,
                "estado": "Pendiente",
                "archivo_original": "cencosud_pago_semanal.xlsx"
            }
        ]
        
        return {
            "liquidaciones": liquidaciones,
            "total": len(liquidaciones),
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener liquidaciones: {str(e)}")

@router.post("/api/cargar")
async def cargar_archivo_liquidacion(
    retail: str,
    archivo: UploadFile = File(...),
    numero_liquidacion: Optional[str] = None
):
    """Cargar archivo de liquidación de retail"""
    try:
        # Validar formato de archivo
        if not archivo.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="Formato de archivo no válido")
        
        # Leer el archivo según el retail
        contenido = await archivo.read()
        
        # Procesar según el retail específico
        resultado = await procesar_liquidacion_retail(retail, contenido, archivo.filename)
        
        return {
            "message": "Liquidación procesada exitosamente",
            "retail": retail,
            "archivo": archivo.filename,
            "ordenes_procesadas": resultado["ordenes_procesadas"],
            "monto_total": resultado["monto_total"],
            "numero_liquidacion": numero_liquidacion or resultado.get("numero_liquidacion")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar liquidación: {str(e)}")

@router.get("/api/ordenes/estado")
async def obtener_estado_ordenes(
    retail: Optional[str] = None,
    numero_orden: Optional[str] = None,
    estado: Optional[str] = None
):
    """Obtener estado de órdenes"""
    try:
        # TODO: Conectar con la base de datos
        ordenes = [
            {
                "numero_orden": "ORD-FAL-2024-001",
                "retail": "Falabella",
                "fecha_orden": "2024-08-01",
                "monto": 85000,
                "estado_pago": "Pagado",
                "fecha_pago": "2024-08-10",
                "numero_liquidacion": "LIQ-FAL-2024-001"
            },
            {
                "numero_orden": "ORD-CEN-2024-002",
                "retail": "Cencosud",
                "fecha_orden": "2024-08-02",
                "monto": 125000,
                "estado_pago": "Pendiente",
                "fecha_pago": None,
                "numero_liquidacion": None
            }
        ]
        
        return {"ordenes": ordenes}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado de órdenes: {str(e)}")

@router.get("/api/ordenes/{numero_orden}")
async def obtener_detalle_orden(numero_orden: str):
    """Obtener detalle específico de una orden"""
    try:
        # TODO: Conectar con la base de datos
        orden = {
            "numero_orden": numero_orden,
            "retail": "Falabella",
            "fecha_orden": "2024-08-01",
            "monto": 85000,
            "estado_pago": "Pagado",
            "fecha_pago": "2024-08-10",
            "numero_liquidacion": "LIQ-FAL-2024-001",
            "productos": [
                {"sku": "PROD-001", "cantidad": 2, "precio_unitario": 42500}
            ]
        }
        
        return orden
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de orden: {str(e)}")

# ===== FUNCIONES AUXILIARES =====

async def procesar_liquidacion_retail(retail: str, contenido: bytes, nombre_archivo: str):
    """Procesar liquidación según el retail específico"""
    
    # Mapeo de procesadores por retail
    procesadores = {
        "falabella": procesar_liquidacion_falabella,
        "cencosud": procesar_liquidacion_cencosud,
        "walmart": procesar_liquidacion_walmart,
        "ripley": procesar_liquidacion_ripley,
        "hites": procesar_liquidacion_hites
    }
    
    procesador = procesadores.get(retail.lower())
    if not procesador:
        raise HTTPException(status_code=400, detail=f"Retail {retail} no soportado")
    
    return await procesador(contenido, nombre_archivo)

async def procesar_liquidacion_falabella(contenido: bytes, nombre_archivo: str):
    """Procesar liquidación específica de Falabella"""
    try:
        # TODO: Implementar lógica específica para Falabella
        # Cada retail tiene formato diferente
        return {
            "ordenes_procesadas": 45,
            "monto_total": 2450000,
            "numero_liquidacion": "LIQ-FAL-2024-001"
        }
    except Exception as e:
        raise Exception(f"Error procesando Falabella: {str(e)}")

async def procesar_liquidacion_cencosud(contenido: bytes, nombre_archivo: str):
    """Procesar liquidación específica de Cencosud"""
    try:
        # Leer archivo Excel
        df = pd.read_excel(BytesIO(contenido), sheet_name='transacciones')
        
        # Validar columnas requeridas
        columnas_requeridas = ['número orden', 'tipo', 'monto a pagar', 'fecha liq.factura', 'número liq.factura']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            raise Exception(f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}")
        
        # Obtener información de la liquidación
        numero_liquidacion = str(df['número liq.factura'].iloc[0]) if len(df) > 0 else None
        fecha_liquidacion = df['fecha liq.factura'].iloc[0] if len(df) > 0 else None
        
        # Estadísticas para el resultado
        ordenes_procesadas = 0
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        monto_total = 0
        monto_ventas = 0
        monto_devoluciones = 0
        errores = []
        
        # TODO: Conectar a la base de datos
        # conn = mysql.connector.connect(
        #     host="localhost",
        #     user="tu_usuario",
        #     password="tu_password",
        #     database="tu_database"
        # )
        # cursor = conn.cursor()
        
        # ID del cliente Cencosud (según tu tabla clientes)
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]  # ID = 2
        
        # Procesar cada fila del Excel
        for index, row in df.iterrows():
            try:
                numero_orden = str(row['número orden'])
                tipo = row['tipo']
                monto_pago = float(row['monto a pagar']) if pd.notna(row['monto a pagar']) else 0
                
                # Convertir tipo
                if tipo == 'Venta':
                    tipo_liquidacion = TipoLiquidacion.venta
                    monto_ventas += monto_pago
                elif tipo == 'Devolución':
                    tipo_liquidacion = TipoLiquidacion.devolucion
                    monto_devoluciones += monto_pago  # Ya viene negativo
                else:
                    tipo_liquidacion = TipoLiquidacion.cancelacion
                
                monto_total += monto_pago
                
                # TODO: Actualizar en la base de datos
                # query = """
                # UPDATE ventas_retail SET 
                #     tipo_liquidacion = %s,
                #     monto_pago_liquidacion = %s,
                #     fecha_liquidacion = %s,
                #     numero_liquidacion = %s,
                #     estado_liquidacion = %s,
                #     archivo_liquidacion = %s,
                #     fecha_procesamiento_liquidacion = NOW()
                # WHERE numero_orden = %s AND cliente_id = %s
                # """
                # 
                # valores = (
                #     tipo_liquidacion.value,
                #     monto_pago,
                #     fecha_liquidacion,
                #     numero_liquidacion,
                #     EstadoLiquidacion.cerrada.value,
                #     nombre_archivo,
                #     numero_orden,
                #     CLIENTE_CENCOSUD_ID
                # )
                # 
                # cursor.execute(query, valores)
                # if cursor.rowcount > 0:
                #     ordenes_actualizadas += 1
                # else:
                #     ordenes_no_encontradas += 1
                #     errores.append(f"Orden {numero_orden} no encontrada en la BD")
                
                ordenes_procesadas += 1
                ordenes_actualizadas += 1  # Simular por ahora
                
            except Exception as e:
                errores.append(f"Error procesando orden {numero_orden}: {str(e)}")
                continue
        
        # TODO: Commit de la transacción
        # conn.commit()
        # cursor.close()
        # conn.close()
        
        return ResultadoProcesamientoLiquidacion(
            success=True,
            message="Liquidación de Cencosud procesada exitosamente",
            retail="cencosud",
            archivo=nombre_archivo,
            numero_liquidacion=numero_liquidacion,
            ordenes_procesadas=ordenes_procesadas,
            ordenes_actualizadas=ordenes_actualizadas,
            ordenes_no_encontradas=ordenes_no_encontradas,
            ordenes_con_error=len(errores),
            monto_total=monto_total,
            monto_ventas=monto_ventas,
            monto_devoluciones=monto_devoluciones,
            fecha_liquidacion=fecha_liquidacion,
            fecha_procesamiento=datetime.now(),
            errores=errores
        )
        
    except Exception as e:
        return ResultadoProcesamientoLiquidacion(
            success=False,
            message=f"Error procesando Cencosud: {str(e)}",
            retail="cencosud",
            archivo=nombre_archivo,
            errores=[str(e)]
        )

async def procesar_liquidacion_walmart(contenido: bytes, nombre_archivo: str):
    """Procesar liquidación específica de Walmart"""
    try:
        # TODO: Implementar lógica específica para Walmart
        return {
            "ordenes_procesadas": 28,
            "monto_total": 1650000,
            "numero_liquidacion": "LIQ-WAL-2024-001"
        }
    except Exception as e:
        raise Exception(f"Error procesando Walmart: {str(e)}")

async def procesar_liquidacion_ripley(contenido: bytes, nombre_archivo: str):
    """Procesar liquidación específica de Ripley"""
    try:
        # TODO: Implementar lógica específica para Ripley
        return {
            "ordenes_procesadas": 38,
            "monto_total": 2100000,
            "numero_liquidacion": "LIQ-RIP-2024-001"
        }
    except Exception as e:
        raise Exception(f"Error procesando Ripley: {str(e)}")

async def procesar_liquidacion_hites(contenido: bytes, nombre_archivo: str):
    """Procesar liquidación específica de Hites"""
    try:
        # TODO: Implementar lógica específica para Hites
        return {
            "ordenes_procesadas": 22,
            "monto_total": 1320000,
            "numero_liquidacion": "LIQ-HIT-2024-001"
        }
    except Exception as e:
        raise Exception(f"Error procesando Hites: {str(e)}")