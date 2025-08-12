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

# Configuración de base de datos desde variables de entorno
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "integracion")
}

# Configuración de retails
RETAIL_CONFIG = {
    "falabella": {"cliente_id": 1, "nombre": "Falabella"},
    "cencosud": {"cliente_id": 2, "nombre": "Cencosud"},
    "walmart": {"cliente_id": 3, "nombre": "Walmart"},
    "ripley": {"cliente_id": 4, "nombre": "Ripley"},
    "hites": {"cliente_id": 5, "nombre": "Hites"}
}

def obtener_conexion_db():
    """Obtener conexión a la base de datos"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error conectando a la base de datos: {str(e)}")

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
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Construir query base
        query = """
        SELECT 
            l.id,
            c.nombre as retail,
            l.numero_liquidacion,
            l.fecha_liquidacion,
            l.monto_total,
            l.cantidad_ordenes,
            l.estado,
            l.archivo_original,
            l.fecha_creacion
        FROM liquidaciones l
        INNER JOIN clientes c ON l.cliente_id = c.id
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if retail:
            query += " AND c.nombre = %s"
            params.append(retail.title())
        
        if fecha_desde:
            query += " AND l.fecha_liquidacion >= %s"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND l.fecha_liquidacion <= %s"
            params.append(fecha_hasta)
        
        # Ordenar por fecha descendente
        query += " ORDER BY l.fecha_liquidacion DESC, l.fecha_creacion DESC"
        
        # Contar total de registros
        count_query = query.replace(
            "SELECT l.id, c.nombre as retail, l.numero_liquidacion, l.fecha_liquidacion, l.monto_total, l.cantidad_ordenes, l.estado, l.archivo_original, l.fecha_creacion",
            "SELECT COUNT(*)"
        )
        
        cursor.execute(count_query, params)
        total = cursor.fetchone()['COUNT(*)']
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        liquidaciones = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "liquidaciones": liquidaciones,
            "total": total,
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
        
        # Validar que el retail esté configurado
        if retail.lower() not in RETAIL_CONFIG:
            raise HTTPException(status_code=400, detail=f"Retail '{retail}' no está configurado")
        
        # Leer el archivo
        contenido = await archivo.read()
        
        # Procesar según el retail específico
        resultado = await procesar_liquidacion_retail(retail, contenido, archivo.filename, numero_liquidacion)
        
        return resultado
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar liquidación: {str(e)}")

@router.get("/api/ordenes/estado")
async def obtener_estado_ordenes(
    retail: Optional[str] = None,
    numero_orden: Optional[str] = None,
    estado: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """Obtener estado de órdenes"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            v.numero_orden,
            c.nombre as retail,
            v.fecha_venta as fecha_orden,
            v.total as monto,
            CASE 
                WHEN v.estado_liquidacion = 'cerrada' THEN 'Pagado'
                WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente'
                ELSE 'Sin procesar'
            END as estado_pago,
            v.fecha_liquidacion as fecha_pago,
            v.numero_liquidacion
        FROM ventas_retail v
        INNER JOIN clientes c ON v.cliente_id = c.id
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if retail:
            query += " AND c.nombre = %s"
            params.append(retail.title())
        
        if numero_orden:
            query += " AND v.numero_orden = %s"
            params.append(numero_orden)
        
        if estado:
            if estado.lower() == 'pagado':
                query += " AND v.estado_liquidacion = 'cerrada'"
            elif estado.lower() == 'pendiente':
                query += " AND v.estado_liquidacion = 'pendiente'"
            else:
                query += " AND (v.estado_liquidacion IS NULL OR v.estado_liquidacion = '')"
        
        # Ordenar
        query += " ORDER BY v.fecha_venta DESC"
        
        # Contar total
        count_query = query.replace(
            "SELECT v.numero_orden, c.nombre as retail, v.fecha_venta as fecha_orden, v.total as monto, CASE WHEN v.estado_liquidacion = 'cerrada' THEN 'Pagado' WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente' ELSE 'Sin procesar' END as estado_pago, v.fecha_liquidacion as fecha_pago, v.numero_liquidacion",
            "SELECT COUNT(*)"
        )
        
        cursor.execute(count_query, params)
        total = cursor.fetchone()['COUNT(*)']
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        ordenes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "ordenes": ordenes,
            "total": total,
            "page": page,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estado de órdenes: {str(e)}")

@router.get("/api/ordenes/{numero_orden}")
async def obtener_detalle_orden(numero_orden: str):
    """Obtener detalle específico de una orden"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información de la orden
        query_orden = """
        SELECT 
            v.numero_orden,
            c.nombre as retail,
            v.fecha_venta as fecha_orden,
            v.total as monto,
            CASE 
                WHEN v.estado_liquidacion = 'cerrada' THEN 'Pagado'
                WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente'
                ELSE 'Sin procesar'
            END as estado_pago,
            v.fecha_liquidacion as fecha_pago,
            v.numero_liquidacion,
            v.tipo_liquidacion,
            v.monto_pago_liquidacion
        FROM ventas_retail v
        INNER JOIN clientes c ON v.cliente_id = c.id
        WHERE v.numero_orden = %s
        """
        
        cursor.execute(query_orden, (numero_orden,))
        orden = cursor.fetchone()
        
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Obtener productos de la orden si existen
        query_productos = """
        SELECT 
            dv.sku,
            dv.cantidad,
            dv.precio_unitario
        FROM detalle_venta dv
        INNER JOIN ventas_retail v ON dv.venta_id = v.id
        WHERE v.numero_orden = %s
        """
        
        cursor.execute(query_productos, (numero_orden,))
        productos = cursor.fetchall()
        
        orden['productos'] = productos
        
        cursor.close()
        conn.close()
        
        return orden
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de orden: {str(e)}")

@router.get("/api/estadisticas")
async def obtener_estadisticas_liquidaciones():
    """Obtener estadísticas generales de liquidaciones"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Estadísticas de liquidaciones
        query_liquidaciones = """
        SELECT 
            COUNT(*) as total_liquidaciones,
            SUM(monto_total) as monto_total_liquidado,
            SUM(cantidad_ordenes) as total_ordenes_liquidadas
        FROM liquidaciones
        WHERE fecha_liquidacion >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
        """
        
        cursor.execute(query_liquidaciones)
        stats_liquidaciones = cursor.fetchone()
        
        # Estadísticas por retail
        query_por_retail = """
        SELECT 
            c.nombre as retail,
            COUNT(*) as cantidad_liquidaciones,
            SUM(l.monto_total) as monto_total,
            SUM(l.cantidad_ordenes) as ordenes_procesadas
        FROM liquidaciones l
        INNER JOIN clientes c ON l.cliente_id = c.id
        WHERE l.fecha_liquidacion >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
        GROUP BY c.id, c.nombre
        ORDER BY monto_total DESC
        """
        
        cursor.execute(query_por_retail)
        stats_por_retail = cursor.fetchall()
        
        # Órdenes pendientes
        query_pendientes = """
        SELECT 
            c.nombre as retail,
            COUNT(*) as ordenes_pendientes,
            SUM(v.total) as monto_pendiente
        FROM ventas_retail v
        INNER JOIN clientes c ON v.cliente_id = c.id
        WHERE (v.estado_liquidacion IS NULL OR v.estado_liquidacion != 'cerrada')
        GROUP BY c.id, c.nombre
        """
        
        cursor.execute(query_pendientes)
        ordenes_pendientes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "liquidaciones": stats_liquidaciones,
            "por_retail": stats_por_retail,
            "ordenes_pendientes": ordenes_pendientes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")

# ===== FUNCIONES AUXILIARES =====

async def procesar_liquidacion_retail(retail: str, contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación según el retail específico"""
    
    retail_lower = retail.lower()
    
    if retail_lower == "cencosud":
        return await procesar_liquidacion_cencosud(contenido, nombre_archivo, numero_liquidacion)
    elif retail_lower == "falabella":
        return await procesar_liquidacion_falabella(contenido, nombre_archivo, numero_liquidacion)
    elif retail_lower == "walmart":
        return await procesar_liquidacion_walmart(contenido, nombre_archivo, numero_liquidacion)
    elif retail_lower == "ripley":
        return await procesar_liquidacion_ripley(contenido, nombre_archivo, numero_liquidacion)
    elif retail_lower == "hites":
        return await procesar_liquidacion_hites(contenido, nombre_archivo, numero_liquidacion)
    else:
        raise HTTPException(status_code=400, detail=f"Procesamiento para retail '{retail}' no implementado")

async def procesar_liquidacion_cencosud(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Cencosud"""
    try:
        # Leer archivo Excel
        df = pd.read_excel(BytesIO(contenido), sheet_name='transacciones')
        
        # Validar columnas requeridas
        columnas_requeridas = ['número orden', 'tipo', 'monto a pagar', 'fecha liq.factura', 'número liq.factura']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            raise Exception(f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}")
        
        # Obtener información de la liquidación del Excel
        numero_liquidacion_excel = str(df['número liq.factura'].iloc[0]) if len(df) > 0 else None
        fecha_liquidacion = df['fecha liq.factura'].iloc[0] if len(df) > 0 else None
        
        # Usar el número proporcionado o el del Excel
        numero_liquidacion_final = numero_liquidacion or numero_liquidacion_excel
        
        # Estadísticas para el resultado
        ordenes_procesadas = 0
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        monto_total = 0
        monto_ventas = 0
        monto_devoluciones = 0
        errores = []
        
        conn = obtener_conexion_db()
        cursor = conn.cursor()
        
        # ID del cliente Cencosud
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
        
        try:
            # Iniciar transacción
            conn.start_transaction()
            
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
                        monto_devoluciones += monto_pago
                    else:
                        tipo_liquidacion = TipoLiquidacion.cancelacion
                    
                    monto_total += monto_pago
                    
                    # Actualizar en la base de datos
                    query_update = """
                    UPDATE ventas_retail SET 
                        tipo_liquidacion = %s,
                        monto_pago_liquidacion = %s,
                        fecha_liquidacion = %s,
                        numero_liquidacion = %s,
                        estado_liquidacion = %s,
                        archivo_liquidacion = %s,
                        fecha_procesamiento_liquidacion = NOW()
                    WHERE numero_orden = %s AND cliente_id = %s
                    """
                    
                    valores = (
                        tipo_liquidacion.value,
                        monto_pago,
                        fecha_liquidacion,
                        numero_liquidacion_final,
                        EstadoLiquidacion.cerrada.value,
                        nombre_archivo,
                        numero_orden,
                        CLIENTE_CENCOSUD_ID
                    )
                    
                    cursor.execute(query_update, valores)
                    if cursor.rowcount > 0:
                        ordenes_actualizadas += 1
                    else:
                        ordenes_no_encontradas += 1
                        errores.append(f"Orden {numero_orden} no encontrada en la BD")
                    
                    ordenes_procesadas += 1
                    
                except Exception as e:
                    errores.append(f"Error procesando orden {numero_orden}: {str(e)}")
                    continue
            
            # Guardar registro de la liquidación
            query_liquidacion = """
            INSERT INTO liquidaciones (
                cliente_id, numero_liquidacion, fecha_liquidacion, 
                monto_total, cantidad_ordenes, estado, archivo_original,
                ordenes_procesadas, ordenes_actualizadas, ordenes_no_encontradas,
                fecha_creacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            valores_liquidacion = (
                CLIENTE_CENCOSUD_ID,
                numero_liquidacion_final,
                fecha_liquidacion,
                monto_total,
                ordenes_procesadas,
                'Procesada',
                nombre_archivo,
                ordenes_procesadas,
                ordenes_actualizadas,
                ordenes_no_encontradas
            )
            
            cursor.execute(query_liquidacion, valores_liquidacion)
            
            # Commit de la transacción
            conn.commit()
            
            return {
                "success": True,
                "message": "Liquidación de Cencosud procesada exitosamente",
                "retail": "Cencosud",
                "archivo": nombre_archivo,
                "numero_liquidacion": numero_liquidacion_final,
                "ordenes_procesadas": ordenes_procesadas,
                "ordenes_actualizadas": ordenes_actualizadas,
                "ordenes_no_encontradas": ordenes_no_encontradas,
                "ordenes_con_error": len(errores),
                "monto_total": monto_total,
                "monto_ventas": monto_ventas,
                "monto_devoluciones": monto_devoluciones,
                "fecha_liquidacion": fecha_liquidacion.isoformat() if fecha_liquidacion else None,
                "fecha_procesamiento": datetime.now().isoformat(),
                "errores": errores
            }
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error procesando Cencosud: {str(e)}",
            "retail": "Cencosud",
            "archivo": nombre_archivo,
            "errores": [str(e)]
        }

async def procesar_liquidacion_falabella(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Falabella"""
    # TODO: Implementar lógica específica para Falabella
    raise HTTPException(status_code=501, detail="Procesamiento para Falabella no implementado aún")

async def procesar_liquidacion_walmart(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Walmart"""
    # TODO: Implementar lógica específica para Walmart
    raise HTTPException(status_code=501, detail="Procesamiento para Walmart no implementado aún")

async def procesar_liquidacion_ripley(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Ripley"""
    # TODO: Implementar lógica específica para Ripley
    raise HTTPException(status_code=501, detail="Procesamiento para Ripley no implementado aún")

async def procesar_liquidacion_hites(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Hites"""
    # TODO: Implementar lógica específica para Hites
    raise HTTPException(status_code=501, detail="Procesamiento para Hites no implementado aún")