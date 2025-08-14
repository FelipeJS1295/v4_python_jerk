from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import os
from typing import Optional
import pandas as pd
from datetime import datetime
import json
import mysql.connector
from io import BytesIO
import traceback

# USAR LA MISMA FUNCIÓN DE CONEXIÓN QUE EL RESTO DEL PROYECTO
from db import conectar_mysql

# Configuración del router
router = APIRouter(prefix="/liquidaciones", tags=["liquidaciones"])
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "..", "templates"))

# Configuración de retails
RETAIL_CONFIG = {
    "falabella": {"cliente_id": 1, "nombre": "Falabella"},
    "cencosud": {"cliente_id": 2, "nombre": "Cencosud"},
    "walmart": {"cliente_id": 3, "nombre": "Walmart"},
    "ripley": {"cliente_id": 4, "nombre": "Ripley"},
    "hites": {"cliente_id": 5, "nombre": "Hites"}
}

def obtener_conexion_db():
    """Obtener conexión a la base de datos usando la configuración del proyecto"""
    try:
        conn = conectar_mysql()
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error conectando a la base de datos: {str(e)}")

# ===== RUTAS DE VISTAS =====

@router.get("/")
async def lista_liquidaciones(request: Request):
    """Vista principal - Lista de liquidaciones"""
    try:
        return templates.TemplateResponse("liquidaciones/lista.html", {
            "request": request
        })
    except Exception as e:
        print(f"Error en vista lista_liquidaciones: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cargar")
async def cargar_liquidacion(request: Request):
    """Vista para cargar nueva liquidación"""
    try:
        return templates.TemplateResponse("liquidaciones/cargar.html", {
            "request": request
        })
    except Exception as e:
        print(f"Error en vista cargar_liquidacion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pendientes")
async def ordenes_pendientes(request: Request):
    """Vista de órdenes pendientes de liquidaciones"""
    try:
        return templates.TemplateResponse("liquidaciones/pendientes.html", {
            "request": request
        })
    except Exception as e:
        print(f"Error en vista ordenes_pendientes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/ordenes-pendientes")
async def obtener_ordenes_pendientes(
    page: int = 1,
    limit: int = 50,
    retail: Optional[str] = None,
    liquidacion_id: Optional[int] = None
):
    """Obtener lista de órdenes pendientes de liquidaciones"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar si la tabla existe
        cursor.execute("SHOW TABLES LIKE 'ordenes_liquidacion_pendientes'")
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            return {
                "ordenes": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "mensaje": "No hay órdenes pendientes"
            }
        
        # Query base
        query = """
        SELECT 
            olp.id,
            olp.numero_orden,
            olp.monto_pago,
            olp.tipo_liquidacion,
            olp.fecha_liquidacion,
            olp.numero_liquidacion,
            olp.fila_excel,
            olp.estado,
            olp.fecha_creacion,
            l.numero_liquidacion as liquidacion_numero,
            CASE 
                WHEN olp.cliente_id = 1 THEN 'Falabella'
                WHEN olp.cliente_id = 2 THEN 'Cencosud' 
                WHEN olp.cliente_id = 3 THEN 'Walmart'
                WHEN olp.cliente_id = 4 THEN 'Ripley'
                WHEN olp.cliente_id = 5 THEN 'Hites'
                ELSE 'Desconocido'
            END as retail
        FROM ordenes_liquidacion_pendientes olp
        LEFT JOIN liquidaciones l ON olp.liquidacion_id = l.id
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if retail:
            retail_info = None
            for key, value in RETAIL_CONFIG.items():
                if value["nombre"].lower() == retail.lower():
                    retail_info = value
                    break
            if retail_info:
                query += " AND olp.cliente_id = %s"
                params.append(retail_info["cliente_id"])
        
        if liquidacion_id:
            query += " AND olp.liquidacion_id = %s"
            params.append(liquidacion_id)
        
        # Solo órdenes pendientes
        query += " AND olp.estado = 'pendiente'"
        
        # Ordenar
        query += " ORDER BY olp.fecha_creacion DESC"
        
        # Contar total
        count_query = query.replace(
            "SELECT olp.id, olp.numero_orden, olp.monto_pago, olp.tipo_liquidacion, olp.fecha_liquidacion, olp.numero_liquidacion, olp.fila_excel, olp.estado, olp.fecha_creacion, l.numero_liquidacion as liquidacion_numero, CASE WHEN olp.cliente_id = 1 THEN 'Falabella' WHEN olp.cliente_id = 2 THEN 'Cencosud' WHEN olp.cliente_id = 3 THEN 'Walmart' WHEN olp.cliente_id = 4 THEN 'Ripley' WHEN olp.cliente_id = 5 THEN 'Hites' ELSE 'Desconocido' END as retail",
            "SELECT COUNT(*) as total"
        )
        
        cursor.execute(count_query, params)
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        ordenes = cursor.fetchall()
        
        # Formatear datos
        ordenes_formateadas = []
        for orden in ordenes:
            orden_formateada = {
                "id": orden["id"],
                "numero_orden": orden["numero_orden"],
                "retail": orden["retail"],
                "monto_pago": float(orden["monto_pago"]) if orden["monto_pago"] else 0,
                "tipo_liquidacion": orden["tipo_liquidacion"],
                "fecha_liquidacion": orden["fecha_liquidacion"].isoformat() if orden["fecha_liquidacion"] else None,
                "numero_liquidacion": orden["numero_liquidacion"],
                "liquidacion_numero": orden["liquidacion_numero"],
                "fila_excel": orden["fila_excel"],
                "estado": orden["estado"],
                "fecha_creacion": orden["fecha_creacion"].isoformat() if orden["fecha_creacion"] else None
            }
            ordenes_formateadas.append(orden_formateada)
        
        return {
            "ordenes": ordenes_formateadas,
            "total": total,
            "page": page,
            "limit": limit,
            "success": True
        }
        
    except mysql.connector.Error as db_error:
        print(f"❌ Error de base de datos: {str(db_error)}")
        return {
            "ordenes": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": f"Error de base de datos: {str(db_error)}",
            "success": False
        }
    except Exception as e:
        print(f"❌ Error al obtener órdenes pendientes: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "ordenes": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": f"Error interno: {str(e)}",
            "success": False
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.delete("/api/ordenes-pendientes/{orden_id}")
async def eliminar_orden_pendiente(orden_id: int):
    """Eliminar una orden pendiente específica"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar que la orden existe
        cursor.execute("SELECT id, numero_orden FROM ordenes_liquidacion_pendientes WHERE id = %s", (orden_id,))
        orden = cursor.fetchone()
        
        if not orden:
            raise HTTPException(status_code=404, detail="Orden pendiente no encontrada")
        
        # Eliminar la orden
        cursor.execute("DELETE FROM ordenes_liquidacion_pendientes WHERE id = %s", (orden_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la orden pendiente")
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Orden pendiente {orden['numero_orden']} eliminada exitosamente",
            "orden_eliminada": {
                "id": orden_id,
                "numero_orden": orden['numero_orden']
            }
        }
        
    except HTTPException:
        raise
    except mysql.connector.Error as db_error:
        if conn:
            conn.rollback()
        print(f"❌ Error de base de datos: {str(db_error)}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(db_error)}")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error al eliminar orden pendiente: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/ordenes")
async def estado_ordenes(request: Request):
    """Vista del estado de órdenes"""
    try:
        return templates.TemplateResponse("liquidaciones/ordenes.html", {
            "request": request
        })
    except Exception as e:
        print(f"Error en vista estado_ordenes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    conn = None
    cursor = None
    
    try:
        print(f"📊 Consultando liquidaciones - Página: {page}, Límite: {limit}")
        
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar si la tabla existe
        cursor.execute("SHOW TABLES LIKE 'liquidaciones'")
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            print("⚠️ Tabla liquidaciones no existe, creándola...")
            crear_tabla_liquidaciones(cursor)
            conn.commit()
            
            # Retornar datos vacíos para nueva tabla
            return {
                "liquidaciones": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "mensaje": "Tabla liquidaciones creada. No hay datos aún."
            }
        
        # Construir query con mapeo directo de cliente_id a nombre
        query = """
        SELECT 
            l.id,
            CASE 
                WHEN l.cliente_id = 1 THEN 'Falabella'
                WHEN l.cliente_id = 2 THEN 'Cencosud' 
                WHEN l.cliente_id = 3 THEN 'Walmart'
                WHEN l.cliente_id = 4 THEN 'Ripley'
                WHEN l.cliente_id = 5 THEN 'Hites'
                ELSE 'Desconocido'
            END as retail,
            l.numero_liquidacion,
            l.fecha_liquidacion,
            l.monto_total,
            l.cantidad_ordenes,
            CASE 
                WHEN l.estado = 'procesada' THEN 'Procesada'
                WHEN l.estado = 'pendiente' THEN 'Pendiente'
                WHEN l.estado = 'error' THEN 'Error'
                ELSE 'Desconocido'
            END as estado,
            l.archivo_original,
            l.fecha_creacion,
            l.ordenes_procesadas,
            l.ordenes_actualizadas,
            l.ordenes_no_encontradas
        FROM liquidaciones l
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if retail:
            # Mapear nombre del retail a cliente_id
            retail_info = None
            for key, value in RETAIL_CONFIG.items():
                if value["nombre"].lower() == retail.lower():
                    retail_info = value
                    break
            
            if retail_info:
                query += " AND l.cliente_id = %s"
                params.append(retail_info["cliente_id"])
        
        if fecha_desde:
            query += " AND l.fecha_liquidacion >= %s"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND l.fecha_liquidacion <= %s"
            params.append(fecha_hasta)
        
        # Ordenar por fecha descendente
        query += " ORDER BY l.fecha_liquidacion DESC, l.fecha_creacion DESC"
        
        print(f"🔍 Query: {query}")
        print(f"📝 Parámetros: {params}")
        
        # Contar total de registros
        count_query = """
        SELECT COUNT(*) as total
        FROM liquidaciones l
        WHERE 1=1
        """
        
        # Aplicar los mismos filtros para el conteo
        count_params = []
        if retail:
            retail_info = None
            for key, value in RETAIL_CONFIG.items():
                if value["nombre"].lower() == retail.lower():
                    retail_info = value
                    break
            if retail_info:
                count_query += " AND l.cliente_id = %s"
                count_params.append(retail_info["cliente_id"])
        
        if fecha_desde:
            count_query += " AND l.fecha_liquidacion >= %s"
            count_params.append(fecha_desde)
        
        if fecha_hasta:
            count_query += " AND l.fecha_liquidacion <= %s"
            count_params.append(fecha_hasta)
        
        cursor.execute(count_query, count_params)
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        print(f"📊 Total de registros encontrados: {total}")
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        liquidaciones = cursor.fetchall()
        
        print(f"✅ Liquidaciones obtenidas: {len(liquidaciones)}")
        
        # Formatear datos para el frontend
        liquidaciones_formateadas = []
        for liq in liquidaciones:
            liquidacion_formateada = {
                "id": liq["id"],
                "retail": liq["retail"],
                "numero_liquidacion": liq["numero_liquidacion"] or "N/A",
                "fecha_liquidacion": liq["fecha_liquidacion"].isoformat() if liq["fecha_liquidacion"] else None,
                "monto_total": float(liq["monto_total"]) if liq["monto_total"] else 0,
                "cantidad_ordenes": liq["cantidad_ordenes"] or 0,
                "estado": liq["estado"],
                "archivo_original": liq["archivo_original"] or "",
                "fecha_creacion": liq["fecha_creacion"].isoformat() if liq["fecha_creacion"] else None,
                "ordenes_procesadas": liq["ordenes_procesadas"] or 0,
                "ordenes_actualizadas": liq["ordenes_actualizadas"] or 0,
                "ordenes_no_encontradas": liq["ordenes_no_encontradas"] or 0
            }
            liquidaciones_formateadas.append(liquidacion_formateada)
        
        return {
            "liquidaciones": liquidaciones_formateadas,
            "total": total,
            "page": page,
            "limit": limit,
            "success": True
        }
        
    except mysql.connector.Error as db_error:
        print(f"❌ Error de base de datos: {str(db_error)}")
        return {
            "liquidaciones": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": f"Error de base de datos: {str(db_error)}",
            "success": False
        }
    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "liquidaciones": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": f"Error interno: {str(e)}",
            "success": False
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.post("/api/cargar")
async def cargar_archivo_liquidacion(
    retail: str = Form(...),
    archivo: UploadFile = File(...),
    numero_liquidacion: Optional[str] = Form(None)
):
    """Cargar archivo de liquidación de retail"""
    try:
        print(f"Recibido: retail={retail}, archivo={archivo.filename}, numero_liquidacion={numero_liquidacion}")
        
        # Validar formato de archivo
        if not archivo.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="Formato de archivo no válido. Solo se permiten .xlsx, .xls, .csv")
        
        # Validar que el retail esté configurado
        if retail.lower() not in RETAIL_CONFIG:
            raise HTTPException(status_code=400, detail=f"Retail '{retail}' no está configurado")
        
        # Leer el archivo
        contenido = await archivo.read()
        print(f"Archivo leído: {len(contenido)} bytes")
        
        # Procesar según el retail específico
        resultado = await procesar_liquidacion_retail(retail, contenido, archivo.filename, numero_liquidacion)
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en cargar_archivo_liquidacion: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
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
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar si la tabla ventas_retail existe
        cursor.execute("SHOW TABLES LIKE 'ventas_retail'")
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            return {
                "ordenes": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "error": "Tabla ventas_retail no existe"
            }
        
        query = """
        SELECT 
            v.numero_orden,
            CASE 
                WHEN v.cliente_id = 1 THEN 'Falabella'
                WHEN v.cliente_id = 2 THEN 'Cencosud' 
                WHEN v.cliente_id = 3 THEN 'Walmart'
                WHEN v.cliente_id = 4 THEN 'Ripley'
                WHEN v.cliente_id = 5 THEN 'Hites'
                ELSE 'Desconocido'
            END as retail,
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
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if retail:
            retail_info = None
            for key, value in RETAIL_CONFIG.items():
                if value["nombre"].lower() == retail.lower():
                    retail_info = value
                    break
            if retail_info:
                query += " AND v.cliente_id = %s"
                params.append(retail_info["cliente_id"])
        
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
            "SELECT v.numero_orden, CASE WHEN v.cliente_id = 1 THEN 'Falabella' WHEN v.cliente_id = 2 THEN 'Cencosud' WHEN v.cliente_id = 3 THEN 'Walmart' WHEN v.cliente_id = 4 THEN 'Ripley' WHEN v.cliente_id = 5 THEN 'Hites' ELSE 'Desconocido' END as retail, v.fecha_venta as fecha_orden, v.total as monto, CASE WHEN v.estado_liquidacion = 'cerrada' THEN 'Pagado' WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente' ELSE 'Sin procesar' END as estado_pago, v.fecha_liquidacion as fecha_pago, v.numero_liquidacion",
            "SELECT COUNT(*) as total"
        )
        
        cursor.execute(count_query, params)
        total_result = cursor.fetchone()
        total = total_result['total'] if total_result else 0
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        ordenes = cursor.fetchall()
        
        return {
            "ordenes": ordenes,
            "total": total,
            "page": page,
            "limit": limit
        }
        
    except mysql.connector.Error as db_error:
        print(f"Error de base de datos en ordenes: {str(db_error)}")
        return {
            "ordenes": [],
            "total": 0,
            "page": page,
            "limit": limit,
            "error": "Error de base de datos"
        }
    except Exception as e:
        print(f"Error en obtener_estado_ordenes: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estado de órdenes: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/api/ordenes/{numero_orden}")
async def obtener_detalle_orden(numero_orden: str):
    """Obtener detalle específico de una orden"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información de la orden
        query_orden = """
        SELECT 
            v.numero_orden,
            CASE 
                WHEN v.cliente_id = 1 THEN 'Falabella'
                WHEN v.cliente_id = 2 THEN 'Cencosud' 
                WHEN v.cliente_id = 3 THEN 'Walmart'
                WHEN v.cliente_id = 4 THEN 'Ripley'
                WHEN v.cliente_id = 5 THEN 'Hites'
                ELSE 'Desconocido'
            END as retail,
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
        WHERE v.numero_orden = %s
        """
        
        cursor.execute(query_orden, (numero_orden,))
        orden = cursor.fetchone()
        
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Intentar obtener productos si la tabla existe
        try:
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
        except:
            orden['productos'] = []
        
        return orden
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en obtener_detalle_orden: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de orden: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/{liquidacion_id}")
async def mostrar_liquidacion(request: Request, liquidacion_id: int):
    """Vista de detalle de liquidación específica"""
    try:
        return templates.TemplateResponse("liquidaciones/show.html", {
            "request": request,
            "liquidacion_id": liquidacion_id
        })
    except Exception as e:
        print(f"Error en vista mostrar_liquidacion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/liquidaciones/{liquidacion_id}")
async def obtener_liquidacion_detalle(liquidacion_id: int):
    """Obtener detalle completo de una liquidación con sus órdenes"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información básica de la liquidación
        query_liquidacion = """
        SELECT 
            l.id,
            CASE 
                WHEN l.cliente_id = 1 THEN 'Falabella'
                WHEN l.cliente_id = 2 THEN 'Cencosud' 
                WHEN l.cliente_id = 3 THEN 'Walmart'
                WHEN l.cliente_id = 4 THEN 'Ripley'
                WHEN l.cliente_id = 5 THEN 'Hites'
                ELSE 'Desconocido'
            END as retail,
            l.numero_liquidacion,
            l.fecha_liquidacion,
            l.monto_total,
            l.cantidad_ordenes,
            CASE 
                WHEN l.estado = 'procesada' THEN 'Procesada'
                WHEN l.estado = 'pendiente' THEN 'Pendiente'
                WHEN l.estado = 'error' THEN 'Error'
                ELSE 'Desconocido'
            END as estado,
            l.archivo_original,
            l.fecha_creacion,
            l.ordenes_procesadas,
            l.ordenes_actualizadas,
            l.ordenes_no_encontradas,
            l.cliente_id
        FROM liquidaciones l
        WHERE l.id = %s
        """
        
        cursor.execute(query_liquidacion, (liquidacion_id,))
        liquidacion = cursor.fetchone()
        
        if not liquidacion:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        
        # Obtener órdenes relacionadas con esta liquidación
        query_ordenes = """
        SELECT 
            v.id,
            v.numero_orden,
            v.fecha_venta as fecha_orden,
            v.total as monto_orden,
            v.monto_pago_liquidacion,
            v.tipo_liquidacion,
            v.fecha_liquidacion,
            v.numero_liquidacion,
            v.estado_liquidacion,
            v.estado_pago,
            CASE 
                WHEN v.estado_liquidacion = 'cerrada' AND v.numero_liquidacion = %s THEN 'Pagada en esta liquidación'
                WHEN v.estado_liquidacion = 'cerrada' AND v.numero_liquidacion != %s THEN 'Pagada en otra liquidación'
                WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente de pago'
                ELSE 'Sin procesar'
            END as estado_pago_detalle,
            CASE 
                WHEN v.numero_liquidacion = %s THEN true
                ELSE false
            END as es_de_esta_liquidacion
        FROM ventas_retail v
        WHERE v.cliente_id = %s 
        AND (
            v.numero_liquidacion = %s 
            OR v.estado_liquidacion IS NULL 
            OR v.estado_liquidacion = 'pendiente'
        )
        ORDER BY 
            es_de_esta_liquidacion DESC,
            v.fecha_venta DESC
        """
        
        numero_liquidacion = liquidacion['numero_liquidacion']
        cliente_id = liquidacion['cliente_id']
        
        cursor.execute(query_ordenes, (
            numero_liquidacion, numero_liquidacion, numero_liquidacion, 
            cliente_id, numero_liquidacion
        ))
        ordenes = cursor.fetchall()
        
        # Separar órdenes pagadas y no pagadas
        ordenes_pagadas = []
        ordenes_no_pagadas = []
        
        for orden in ordenes:
            if orden['es_de_esta_liquidacion']:
                ordenes_pagadas.append({
                    'id': orden['id'],
                    'numero_orden': orden['numero_orden'],
                    'fecha_orden': orden['fecha_orden'].isoformat() if orden['fecha_orden'] else None,
                    'monto_orden': float(orden['monto_orden']) if orden['monto_orden'] else 0,
                    'monto_pago': float(orden['monto_pago_liquidacion']) if orden['monto_pago_liquidacion'] else 0,
                    'tipo_liquidacion': orden['tipo_liquidacion'] or 'venta',
                    'estado_pago': orden['estado_pago_detalle']
                })
            else:
                ordenes_no_pagadas.append({
                    'id': orden['id'],
                    'numero_orden': orden['numero_orden'],
                    'fecha_orden': orden['fecha_orden'].isoformat() if orden['fecha_orden'] else None,
                    'monto_orden': float(orden['monto_orden']) if orden['monto_orden'] else 0,
                    'estado_pago': orden['estado_pago_detalle']
                })
        
        # Calcular estadísticas
        total_ordenes_pagadas = len(ordenes_pagadas)
        total_ordenes_no_pagadas = len(ordenes_no_pagadas)
        monto_total_pagado = sum(orden['monto_pago'] for orden in ordenes_pagadas)
        monto_total_pendiente = sum(orden['monto_orden'] for orden in ordenes_no_pagadas)
        
        # Separar por tipo de liquidación
        ordenes_ventas = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'venta']
        ordenes_devoluciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'devolucion']
        ordenes_cancelaciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'cancelacion']
        
        monto_ventas = sum(orden['monto_pago'] for orden in ordenes_ventas)
        monto_devoluciones = sum(orden['monto_pago'] for orden in ordenes_devoluciones)
        monto_cancelaciones = sum(orden['monto_pago'] for orden in ordenes_cancelaciones)
        
        return {
            "liquidacion": {
                "id": liquidacion['id'],
                "retail": liquidacion['retail'],
                "numero_liquidacion": liquidacion['numero_liquidacion'],
                "fecha_liquidacion": liquidacion['fecha_liquidacion'].isoformat() if liquidacion['fecha_liquidacion'] else None,
                "monto_total": float(liquidacion['monto_total']) if liquidacion['monto_total'] else 0,
                "cantidad_ordenes": liquidacion['cantidad_ordenes'] or 0,
                "estado": liquidacion['estado'],
                "archivo_original": liquidacion['archivo_original'],
                "fecha_creacion": liquidacion['fecha_creacion'].isoformat() if liquidacion['fecha_creacion'] else None,
                "ordenes_procesadas": liquidacion['ordenes_procesadas'] or 0,
                "ordenes_actualizadas": liquidacion['ordenes_actualizadas'] or 0,
                "ordenes_no_encontradas": liquidacion['ordenes_no_encontradas'] or 0
            },
            "estadisticas": {
                "total_ordenes_pagadas": total_ordenes_pagadas,
                "total_ordenes_no_pagadas": total_ordenes_no_pagadas,
                "monto_total_pagado": monto_total_pagado,
                "monto_total_pendiente": monto_total_pendiente,
                "monto_ventas": monto_ventas,
                "monto_devoluciones": monto_devoluciones,
                "monto_cancelaciones": monto_cancelaciones,
                "cantidad_ventas": len(ordenes_ventas),
                "cantidad_devoluciones": len(ordenes_devoluciones),
                "cantidad_cancelaciones": len(ordenes_cancelaciones)
            },
            "ordenes_pagadas": ordenes_pagadas,
            "ordenes_no_pagadas": ordenes_no_pagadas,
            "success": True
        }
        
    except HTTPException:
        raise
    except mysql.connector.Error as db_error:
        print(f"❌ Error de base de datos al obtener detalle: {str(db_error)}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(db_error)}")
    except Exception as e:
        print(f"❌ Error al obtener detalle de liquidación: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.delete("/api/liquidaciones/{liquidacion_id}")
async def eliminar_liquidacion(liquidacion_id: int):
    """Eliminar una liquidación específica"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar que la liquidación existe
        cursor.execute("SELECT id, numero_liquidacion, archivo_original FROM liquidaciones WHERE id = %s", (liquidacion_id,))
        liquidacion = cursor.fetchone()
        
        if not liquidacion:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        
        # Eliminar la liquidación
        cursor.execute("DELETE FROM liquidaciones WHERE id = %s", (liquidacion_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar la liquidación")
        
        conn.commit()
        
        print(f"✅ Liquidación {liquidacion_id} eliminada exitosamente")
        
        return {
            "success": True,
            "message": f"Liquidación {liquidacion['numero_liquidacion']} eliminada exitosamente",
            "liquidacion_eliminada": {
                "id": liquidacion_id,
                "numero_liquidacion": liquidacion['numero_liquidacion'],
                "archivo_original": liquidacion['archivo_original']
            }
        }
        
    except HTTPException:
        raise
    except mysql.connector.Error as db_error:
        if conn:
            conn.rollback()
        print(f"❌ Error de base de datos al eliminar liquidación: {str(db_error)}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(db_error)}")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error al eliminar liquidación: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/api/estadisticas")
async def obtener_estadisticas_liquidaciones():
    """Obtener estadísticas generales de liquidaciones"""
    conn = None
    cursor = None
    
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Estadísticas básicas si las tablas existen
        stats_liquidaciones = {"total_liquidaciones": 0, "monto_total_liquidado": 0, "total_ordenes_liquidadas": 0}
        
        try:
            # Estadísticas de liquidaciones
            query_liquidaciones = """
            SELECT 
                COUNT(*) as total_liquidaciones,
                COALESCE(SUM(monto_total), 0) as monto_total_liquidado,
                COALESCE(SUM(cantidad_ordenes), 0) as total_ordenes_liquidadas
            FROM liquidaciones
            WHERE fecha_liquidacion >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
            """
            
            cursor.execute(query_liquidaciones)
            stats_liquidaciones = cursor.fetchone() or stats_liquidaciones
            
        except mysql.connector.Error:
            pass  # Tabla no existe, usar valores por defecto
        
        return {
            "liquidaciones": stats_liquidaciones,
            "por_retail": [],
            "ordenes_pendientes": []
        }
        
    except Exception as e:
        print(f"Error en obtener_estadisticas_liquidaciones: {str(e)}")
        return {
            "liquidaciones": {"total_liquidaciones": 0, "monto_total_liquidado": 0, "total_ordenes_liquidadas": 0},
            "por_retail": [],
            "ordenes_pendientes": []
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ===== FUNCIONES AUXILIARES =====

def crear_tabla_liquidaciones(cursor):
    """Crear tabla liquidaciones si no existe"""
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS liquidaciones (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cliente_id INT,
            numero_liquidacion VARCHAR(100),
            fecha_liquidacion DATE,
            monto_total DECIMAL(15,2) DEFAULT 0,
            cantidad_ordenes INT DEFAULT 0,
            estado ENUM('pendiente', 'procesada', 'error') DEFAULT 'pendiente',
            archivo_original VARCHAR(255),
            ordenes_procesadas INT DEFAULT 0,
            ordenes_actualizadas INT DEFAULT 0,
            ordenes_no_encontradas INT DEFAULT 0,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_cliente_fecha (cliente_id, fecha_liquidacion),
            INDEX idx_numero_liquidacion (numero_liquidacion),
            INDEX idx_fecha_liquidacion (fecha_liquidacion)
        )
        """)
        print("✅ Tabla liquidaciones creada/verificada")
    except Exception as e:
        print(f"Error creando tabla liquidaciones: {str(e)}")

def crear_tabla_ordenes_pendientes(cursor):
    """Crear tabla para órdenes no encontradas en liquidaciones"""
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_liquidacion_pendientes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            liquidacion_id INT,
            numero_orden VARCHAR(100),
            monto_pago DECIMAL(15,2) DEFAULT 0,
            tipo_liquidacion ENUM('venta', 'devolucion', 'cancelacion') DEFAULT 'venta',
            fecha_liquidacion DATE,
            numero_liquidacion VARCHAR(100),
            fecha_procesamiento_liquidacion VARCHAR(255),
            estado_liquidacion_excel VARCHAR(100),
            cliente_id INT,
            fila_excel INT,
            data_completa JSON,
            estado ENUM('pendiente', 'procesada', 'error') DEFAULT 'pendiente',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_liquidacion_id (liquidacion_id),
            INDEX idx_numero_orden (numero_orden),
            INDEX idx_cliente_id (cliente_id),
            INDEX idx_estado (estado),
            
            FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE
        )
        """)
        print("✅ Tabla ordenes_liquidacion_pendientes creada/verificada")
    except Exception as e:
        print(f"Error creando tabla ordenes_liquidacion_pendientes: {str(e)}")

# ===== FUNCIONES AUXILIARES =====

def crear_tabla_liquidaciones(cursor):
    """Crear tabla liquidaciones si no existe"""
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS liquidaciones (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cliente_id INT,
            numero_liquidacion VARCHAR(100),
            fecha_liquidacion DATE,
            monto_total DECIMAL(15,2) DEFAULT 0,
            cantidad_ordenes INT DEFAULT 0,
            estado ENUM('pendiente', 'procesada', 'error') DEFAULT 'pendiente',
            archivo_original VARCHAR(255),
            ordenes_procesadas INT DEFAULT 0,
            ordenes_actualizadas INT DEFAULT 0,
            ordenes_no_encontradas INT DEFAULT 0,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_cliente_fecha (cliente_id, fecha_liquidacion),
            INDEX idx_numero_liquidacion (numero_liquidacion),
            INDEX idx_fecha_liquidacion (fecha_liquidacion)
        )
        """)
        
        # También crear la tabla de órdenes pendientes
        crear_tabla_ordenes_pendientes(cursor)
        
        print("✅ Tabla liquidaciones creada/verificada")
    except Exception as e:
        print(f"Error creando tabla liquidaciones: {str(e)}")

async def procesar_liquidacion_retail(retail: str, contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación según el retail específico"""
    
    retail_lower = retail.lower()
    
    if retail_lower == "cencosud":
        return await procesar_liquidacion_cencosud(contenido, nombre_archivo, numero_liquidacion)
    else:
        # Para otros retails que no están implementados
        return {
            "success": False,
            "message": f"Procesamiento para retail '{retail}' no implementado aún",
            "retail": retail,
            "archivo": nombre_archivo,
            "errores": [f"El procesamiento para {retail} está en desarrollo"]
        }

async def procesar_liquidacion_cencosud(contenido: bytes, nombre_archivo: str, numero_liquidacion: Optional[str] = None):
    """Procesar liquidación específica de Cencosud - CORREGIDO PARA MANEJAR NaN"""
    conn = None
    cursor = None
    
    try:
        print(f"🔄 Iniciando procesamiento de archivo Cencosud: {nombre_archivo}")
        
        # Leer archivo Excel con manejo robusto
        try:
            # Leer todas las hojas disponibles primero
            excel_file = pd.ExcelFile(BytesIO(contenido))
            hojas_disponibles = excel_file.sheet_names
            print(f"📊 Hojas disponibles en Excel: {hojas_disponibles}")
            
            # Buscar la hoja 'transacciones' (con diferentes variaciones)
            hoja_transacciones = None
            for hoja in hojas_disponibles:
                if 'transacciones' in hoja.lower() or 'transaccion' in hoja.lower():
                    hoja_transacciones = hoja
                    break
            
            if not hoja_transacciones:
                # Si no encuentra 'transacciones', usar la primera hoja
                hoja_transacciones = hojas_disponibles[0]
                print(f"⚠️ No se encontró hoja 'transacciones', usando: {hoja_transacciones}")
            
            # Leer la hoja con configuración robusta
            df = pd.read_excel(
                BytesIO(contenido), 
                sheet_name=hoja_transacciones,
                na_values=['', 'nan', 'NaN', 'null', None],  # Valores que se consideran NaN
                keep_default_na=True,
                dtype=str  # Leer todo como string inicialmente
            )
            
            print(f"📋 Archivo leído exitosamente. Filas: {len(df)}, Columnas: {len(df.columns)}")
            print(f"📝 Columnas encontradas: {list(df.columns)}")
            
        except Exception as e:
            print(f"❌ Error leyendo archivo Excel: {str(e)}")
            raise Exception(f"Error leyendo archivo Excel: {str(e)}")
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip().str.lower()
        
        # Validar columnas requeridas para Cencosud (en minúsculas)
        columnas_requeridas_map = {
            'número orden': ['número orden', 'numero orden', 'nro orden', 'orden'],
            'tipo': ['tipo', 'tipo liquidacion', 'tipo_liquidacion'],
            'monto a pagar': ['monto a pagar', 'monto pagar', 'monto', 'valor'],
            'fecha liq.factura': ['fecha liq.factura', 'fecha liquidacion', 'fecha liq', 'fecha'],
            'número liq.factura': ['número liq.factura', 'numero liq.factura', 'nro liquidacion'],
            'nro solicitud liq.factura': ['nro solicitud liq.factura', 'solicitud', 'nro solicitud'],
            'estado de liq.factura': ['estado de liq.factura', 'estado liquidacion', 'estado']
        }
        
        # Mapear columnas encontradas a nombres estándar
        columnas_mapeadas = {}
        for columna_std, variaciones in columnas_requeridas_map.items():
            columna_encontrada = None
            for variacion in variaciones:
                if variacion in df.columns:
                    columna_encontrada = variacion
                    break
            
            if columna_encontrada:
                columnas_mapeadas[columna_std] = columna_encontrada
                print(f"✅ Columna '{columna_std}' mapeada a '{columna_encontrada}'")
            else:
                print(f"❌ Columna '{columna_std}' no encontrada en: {list(df.columns)}")
        
        # Verificar que se encontraron las columnas esenciales
        columnas_faltantes = [col for col in columnas_requeridas_map.keys() if col not in columnas_mapeadas]
        
        if columnas_faltantes:
            raise Exception(f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}. Columnas disponibles: {', '.join(df.columns)}")
        
        # Renombrar columnas para estandarizar
        df_renamed = df.rename(columns={v: k for k, v in columnas_mapeadas.items()})
        
        # Limpiar datos y manejar valores NaN de forma segura
        print(f"🧹 Limpiando datos...")
        
        # Limpiar y validar datos fila por fila
        filas_validas = []
        errores_fila = []
        
        for index, row in df_renamed.iterrows():
            try:
                # Extraer y limpiar cada campo de forma segura
                numero_orden = str(row.get('número orden', '')).strip()
                if numero_orden in ['nan', 'NaN', '', 'None']:
                    numero_orden = ''
                
                tipo = str(row.get('tipo', '')).strip()
                if tipo in ['nan', 'NaN', '', 'None']:
                    tipo = 'venta'  # Valor por defecto
                
                # Manejar monto de forma segura
                monto_raw = row.get('monto a pagar', 0)
                try:
                    if pd.isna(monto_raw) or str(monto_raw).strip() in ['nan', 'NaN', '', 'None']:
                        monto_pago = 0.0
                    else:
                        monto_pago = float(str(monto_raw).replace(',', '.'))
                except (ValueError, TypeError):
                    monto_pago = 0.0
                
                # Manejar fecha de forma segura
                fecha_raw = row.get('fecha liq.factura')
                fecha_liquidacion = None
                if pd.notna(fecha_raw) and str(fecha_raw).strip() not in ['nan', 'NaN', '', 'None']:
                    try:
                        if isinstance(fecha_raw, str):
                            fecha_liquidacion = pd.to_datetime(fecha_raw).date()
                        else:
                            fecha_liquidacion = fecha_raw.date() if hasattr(fecha_raw, 'date') else None
                    except:
                        fecha_liquidacion = None
                
                # Otros campos
                numero_liquidacion_fila = str(row.get('número liq.factura', '')).strip()
                if numero_liquidacion_fila in ['nan', 'NaN', '', 'None']:
                    numero_liquidacion_fila = ''
                
                nro_solicitud = str(row.get('nro solicitud liq.factura', '')).strip()
                if nro_solicitud in ['nan', 'NaN', '', 'None']:
                    nro_solicitud = ''
                
                estado_liquidacion_excel = str(row.get('estado de liq.factura', '')).strip()
                if estado_liquidacion_excel in ['nan', 'NaN', '', 'None']:
                    estado_liquidacion_excel = 'pendiente'
                
                # Validar que al menos tengamos número de orden
                if not numero_orden:
                    errores_fila.append(f"Fila {index + 2}: Número de orden vacío")
                    continue
                
                fila_procesada = {
                    'numero_orden_excel': numero_orden,
                    'tipo': tipo,
                    'monto_pago': monto_pago,
                    'fecha_liquidacion': fecha_liquidacion,
                    'numero_liquidacion_fila': numero_liquidacion_fila,
                    'nro_solicitud': nro_solicitud,
                    'estado_liquidacion_excel': estado_liquidacion_excel,
                    'fila_excel': index + 2  # +2 porque Excel empieza en 1 y hay header
                }
                
                filas_validas.append(fila_procesada)
                print(f"✅ Fila {index + 2}: Orden {numero_orden} procesada")
                
            except Exception as e:
                error_msg = f"Fila {index + 2}: Error procesando datos - {str(e)}"
                errores_fila.append(error_msg)
                print(f"⚠️ {error_msg}")
                continue
        
        if not filas_validas:
            raise Exception(f"No se pudieron procesar filas válidas. Errores: {'; '.join(errores_fila[:5])}")
        
        print(f"📊 Filas válidas procesadas: {len(filas_validas)}")
        
        # Obtener información de la liquidación del primer registro válido
        primera_fila = filas_validas[0]
        numero_liquidacion_excel = primera_fila['numero_liquidacion_fila']
        fecha_liquidacion = primera_fila['fecha_liquidacion']
        
        # Usar el número proporcionado o el del Excel
        numero_liquidacion_final = numero_liquidacion or numero_liquidacion_excel
        if not numero_liquidacion_final:
            numero_liquidacion_final = f"LIQ-CEN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        print(f"📄 Número de liquidación final: {numero_liquidacion_final}")
        
        # Conectar a la base de datos
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        conn.autocommit = False
        
        # ID del cliente Cencosud
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
        
        try:
            # Crear tablas si no existen
            crear_tabla_liquidaciones(cursor)
            crear_tabla_ordenes_pendientes(cursor)
            
            print(f"🔍 Procesando {len(filas_validas)} órdenes del Excel")
            
            # PASO 1: SEPARAR órdenes encontradas y no encontradas
            ordenes_no_encontradas = []
            ordenes_validas = []
            
            for fila_data in filas_validas:
                numero_orden_excel = fila_data['numero_orden_excel']
                
                # PARA CENCOSUD: Agregar '0' al final del número de orden del Excel
                numero_orden_bd = numero_orden_excel + '0'
                
                print(f"🔍 Fila {fila_data['fila_excel']}: Excel={numero_orden_excel} -> BD={numero_orden_bd}")
                
                # Buscar la orden en ventas_retail
                query_buscar = """
                SELECT id, numero_orden FROM ventas_retail 
                WHERE numero_orden = %s AND cliente_id = %s
                """
                
                cursor.execute(query_buscar, (numero_orden_bd, CLIENTE_CENCOSUD_ID))
                venta_encontrada = cursor.fetchone()
                
                if venta_encontrada:
                    fila_data['numero_orden_bd'] = numero_orden_bd
                    fila_data['venta_id'] = venta_encontrada['id']
                    ordenes_validas.append(fila_data)
                    print(f"✅ Orden {numero_orden_excel} encontrada en BD como {numero_orden_bd}")
                else:
                    fila_data['numero_orden_bd'] = numero_orden_bd
                    ordenes_no_encontradas.append(fila_data)
                    print(f"⚠️ Orden {numero_orden_excel} NO encontrada - se guardará como pendiente")
            
            print(f"📊 Resumen: {len(ordenes_validas)} encontradas, {len(ordenes_no_encontradas)} no encontradas")
            
            # PASO 2: GUARDAR LIQUIDACIÓN (siempre se guarda)
            monto_total = sum(fila['monto_pago'] for fila in filas_validas)
            
            # Determinar estado de la liquidación
            if len(ordenes_no_encontradas) == 0:
                estado_liquidacion = 'procesada'  # Todas las órdenes fueron encontradas
            elif len(ordenes_validas) == 0:
                estado_liquidacion = 'error'      # Ninguna orden fue encontrada
            else:
                estado_liquidacion = 'procesada'  # Parcialmente procesada (pero exitosa)
            
            # Insertar registro de liquidación
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
                len(filas_validas),  # Total de órdenes en el Excel
                estado_liquidacion,
                nombre_archivo,
                len(filas_validas),  # Órdenes procesadas
                len(ordenes_validas),  # Órdenes actualizadas exitosamente
                len(ordenes_no_encontradas)  # Órdenes no encontradas
            )
            
            cursor.execute(query_liquidacion, valores_liquidacion)
            liquidacion_id = cursor.lastrowid
            
            print(f"✅ Liquidación {liquidacion_id} guardada con estado: {estado_liquidacion}")
            
            # PASO 3: ACTUALIZAR órdenes encontradas en ventas_retail
            ordenes_actualizadas = 0
            errores_actualizacion = []
            
            for fila_data in ordenes_validas:
                try:
                    numero_orden_excel = fila_data['numero_orden_excel']
                    numero_orden_bd = fila_data['numero_orden_bd']
                    
                    tipo = fila_data['tipo']
                    monto_pago = fila_data['monto_pago']
                    fecha_liquidacion_fila = fila_data['fecha_liquidacion']
                    numero_liquidacion_fila = fila_data['numero_liquidacion_fila']
                    nro_solicitud = fila_data['nro_solicitud']
                    estado_liquidacion_excel = fila_data['estado_liquidacion_excel']
                    
                    print(f"📝 Actualizando orden Excel:{numero_orden_excel} -> BD:{numero_orden_bd}")
                    
                    # Mapear tipo a enum
                    if tipo.lower() in ['venta', 'ventas']:
                        tipo_liquidacion = 'venta'
                    elif tipo.lower() in ['devolución', 'devolucion', 'devoluciones']:
                        tipo_liquidacion = 'devolucion'
                    else:
                        tipo_liquidacion = 'cancelacion'
                    
                    # Mapear estado de liquidación
                    if estado_liquidacion_excel.lower() in ['pagada', 'pagado', 'cerrada', 'finalizada']:
                        estado_liquidacion = 'cerrada'
                        estado_pago = 'pagada'
                    elif estado_liquidacion_excel.lower() in ['pendiente', 'proceso']:
                        estado_liquidacion = 'pendiente'
                        estado_pago = 'pendiente'
                    else:
                        estado_liquidacion = 'pendiente'
                        estado_pago = 'pendiente'
                    
                    # Actualizar la orden existente usando el número de BD (con el 0)
                    query_update = """
                    UPDATE ventas_retail SET 
                        monto_pago_liquidacion = %s,
                        tipo_liquidacion = %s,
                        fecha_liquidacion = %s,
                        numero_liquidacion = %s,
                        fecha_procesamiento_liquidacion = %s,
                        estado_liquidacion = %s,
                        estado_pago = %s
                    WHERE numero_orden = %s AND cliente_id = %s
                    """
                    
                    valores = (
                        monto_pago,                    # monto_pago_liquidacion
                        tipo_liquidacion,              # tipo_liquidacion  
                        fecha_liquidacion_fila,        # fecha_liquidacion
                        numero_liquidacion_fila,       # numero_liquidacion
                        nro_solicitud,                 # fecha_procesamiento_liquidacion
                        estado_liquidacion,            # estado_liquidacion
                        estado_pago,                   # estado_pago
                        numero_orden_bd,               # WHERE numero_orden (usar número BD con 0)
                        CLIENTE_CENCOSUD_ID           # WHERE cliente_id
                    )
                    
                    cursor.execute(query_update, valores)
                    
                    if cursor.rowcount > 0:
                        ordenes_actualizadas += 1
                        print(f"✅ Orden {numero_orden_excel} actualizada exitosamente en BD")
                    else:
                        errores_actualizacion.append(f"Orden {numero_orden_excel} no se pudo actualizar")
                        print(f"⚠️ Orden {numero_orden_excel} no se pudo actualizar")
                    
                except Exception as e:
                    error_msg = f"Error actualizando orden {numero_orden_excel}: {str(e)}"
                    errores_actualizacion.append(error_msg)
                    print(f"❌ {error_msg}")
                    continue
            
            # PASO 4: GUARDAR órdenes no encontradas como pendientes
            ordenes_pendientes_guardadas = 0
            
            for fila_data in ordenes_no_encontradas:
                try:
                    query_pendiente = """
                    INSERT INTO ordenes_liquidacion_pendientes (
                        liquidacion_id, numero_orden, monto_pago, tipo_liquidacion,
                        fecha_liquidacion, numero_liquidacion, fecha_procesamiento_liquidacion,
                        estado_liquidacion_excel, cliente_id, fila_excel, data_completa,
                        estado, fecha_creacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', NOW())
                    """
                    
                    # Mapear tipo para pendientes
                    tipo = fila_data['tipo']
                    if tipo.lower() in ['venta', 'ventas']:
                        tipo_liquidacion = 'venta'
                    elif tipo.lower() in ['devolución', 'devolucion', 'devoluciones']:
                        tipo_liquidacion = 'devolucion'
                    else:
                        tipo_liquidacion = 'cancelacion'
                    
                    valores_pendiente = (
                        liquidacion_id,
                        fila_data['numero_orden_excel'],
                        fila_data['monto_pago'],
                        tipo_liquidacion,
                        fila_data['fecha_liquidacion'],
                        fila_data['numero_liquidacion_fila'],
                        fila_data['nro_solicitud'],
                        fila_data['estado_liquidacion_excel'],
                        CLIENTE_CENCOSUD_ID,
                        fila_data['fila_excel'],
                        json.dumps(fila_data)  # Guardar todos los datos como JSON
                    )
                    
                    cursor.execute(query_pendiente, valores_pendiente)
                    ordenes_pendientes_guardadas += 1
                    
                except Exception as e:
                    print(f"❌ Error guardando orden pendiente {fila_data['numero_orden_excel']}: {str(e)}")
                    continue
            
            # Commit de la transacción
            conn.commit()
            print("✅ Transacción confirmada exitosamente")
            
            print(f"✅ Liquidación procesada exitosamente:")
            print(f"   - Órdenes procesadas: {len(filas_validas)}")
            print(f"   - Órdenes actualizadas: {ordenes_actualizadas}")
            print(f"   - Órdenes pendientes: {ordenes_pendientes_guardadas}")
            print(f"   - Monto total: {monto_total}")
            
            # Preparar respuesta
            resultado = {
                "success": True,
                "message": "Liquidación de Cencosud procesada exitosamente",
                "retail": "Cencosud",
                "archivo": nombre_archivo,
                "numero_liquidacion": numero_liquidacion_final,
                "ordenes_procesadas": len(filas_validas),
                "ordenes_actualizadas": ordenes_actualizadas,
                "ordenes_no_encontradas": len(ordenes_no_encontradas),
                "ordenes_pendientes_guardadas": ordenes_pendientes_guardadas,
                "monto_total": monto_total,
                "fecha_liquidacion": fecha_liquidacion.isoformat() if fecha_liquidacion else None,
                "fecha_procesamiento": datetime.now().isoformat(),
                "errores": errores_actualizacion[:10] if errores_actualizacion else []
            }
            
            # Si hay órdenes pendientes, agregar información adicional
            if ordenes_no_encontradas:
                resultado["detalle_ordenes_faltantes"] = [
                    {
                        "numero_orden": fila['numero_orden_excel'],
                        "fila_excel": fila['fila_excel'],
                        "monto": fila['monto_pago']
                    }
                    for fila in ordenes_no_encontradas[:20]  # Máximo 20 para el response
                ]
                
                resultado["message"] = f"Liquidación procesada: {ordenes_actualizadas} órdenes actualizadas, {len(ordenes_no_encontradas)} órdenes guardadas como pendientes"
            
            return resultado
            
        except Exception as e:
            try:
                conn.rollback()
                print(f"🔄 Transacción revertida debido a error")
            except:
                pass
            print(f"❌ Error en transacción: {str(e)}")
            raise e
            
        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
                print("🔌 Conexión a BD cerrada")
            except:
                pass
        
    except Exception as e:
        print(f"❌ Error general procesando Cencosud: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Error procesando archivo de Cencosud: {str(e)}",
            "retail": "Cencosud",
            "archivo": nombre_archivo,
            "ordenes_procesadas": 0,
            "ordenes_actualizadas": 0,
            "ordenes_no_encontradas": 0,
            "monto_total": 0,
            "errores": [str(e)]
        }