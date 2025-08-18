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
    """Obtener detalle completo de una liquidación con sus órdenes asociadas directamente"""
    conn = None
    cursor = None
    
    try:
        print(f"🔍 Obteniendo detalle de liquidación ID: {liquidacion_id}")
        
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Verificar que las tablas existan
        cursor.execute("SHOW TABLES LIKE 'liquidaciones'")
        tabla_liquidaciones = cursor.fetchone()
        
        if not tabla_liquidaciones:
            print("⚠️ Tabla liquidaciones no existe")
            raise HTTPException(status_code=404, detail="Tabla liquidaciones no encontrada")
        
        cursor.execute("SHOW TABLES LIKE 'ventas_retail'")
        tabla_ventas = cursor.fetchone()
        
        if not tabla_ventas:
            print("⚠️ Tabla ventas_retail no existe")
            # Crear respuesta con datos básicos sin órdenes
            return await obtener_liquidacion_sin_ordenes(cursor, liquidacion_id)
        
        # 2. Obtener información básica de la liquidación
        query_liquidacion = """
        SELECT 
            l.id,
            l.cliente_id,
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
            l.estado,
            l.archivo_original,
            l.fecha_creacion,
            l.ordenes_procesadas,
            l.ordenes_actualizadas,
            l.ordenes_no_encontradas
        FROM liquidaciones l
        WHERE l.id = %s
        """
        
        cursor.execute(query_liquidacion, (liquidacion_id,))
        liquidacion = cursor.fetchone()
        
        if not liquidacion:
            print(f"❌ Liquidación {liquidacion_id} no encontrada")
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        
        print(f"✅ Liquidación encontrada: {liquidacion['numero_liquidacion']}")
        
        # 3. Verificar si la columna liquidacion_id existe en ventas_retail
        try:
            cursor.execute("DESCRIBE ventas_retail")
            columnas = cursor.fetchall()
            columnas_nombres = [col['Field'] for col in columnas]
            
            if 'liquidacion_id' not in columnas_nombres:
                print("⚠️ Columna liquidacion_id no existe en ventas_retail")
                # Buscar órdenes por número de liquidación como fallback
                return await obtener_ordenes_por_numero_liquidacion(cursor, liquidacion, liquidacion_id)
            
        except Exception as e:
            print(f"⚠️ Error verificando columnas: {str(e)}")
            return await obtener_liquidacion_sin_ordenes_simple(liquidacion)
        
        # 4. Obtener órdenes asociadas a esta liquidación
        query_ordenes = """
        SELECT 
            v.id,
            v.numero_orden,
            v.fecha_venta AS fecha_orden,
            v.total AS monto_orden,
            v.monto_pago_liquidacion,
            v.tipo_liquidacion,
            v.fecha_liquidacion,
            v.numero_liquidacion,
            v.estado_liquidacion,
            v.estado_pago
        FROM ventas_retail v
        WHERE v.liquidacion_id = %s
        ORDER BY v.fecha_venta DESC
        """
        
        cursor.execute(query_ordenes, (liquidacion_id,))
        ordenes = cursor.fetchall()
        
        print(f"📊 Órdenes encontradas: {len(ordenes)}")
        
        # 5. Procesar órdenes y estadísticas
        ordenes_pagadas = []
        ordenes_no_pagadas = []
        
        for orden in ordenes:
            registro = {
                'id': orden['id'],
                'numero_orden': orden['numero_orden'],
                'fecha_orden': orden['fecha_orden'].isoformat() if orden['fecha_orden'] else None,
                'monto_orden': float(orden['monto_orden']) if orden['monto_orden'] else 0,
                'tipo_liquidacion': orden['tipo_liquidacion'] or 'venta',
                'estado_pago': orden['estado_pago'] or 'pendiente'
            }
            
            # Clasificar según estado de pago
            if orden['estado_pago'] and orden['estado_pago'].lower() in ['pagado', 'pagada', 'cerrada']:
                registro['monto_pago'] = float(orden['monto_pago_liquidacion']) if orden['monto_pago_liquidacion'] else 0
                ordenes_pagadas.append(registro)
            else:
                ordenes_no_pagadas.append(registro)
        
        # 6. Calcular estadísticas
        total_ordenes_pagadas = len(ordenes_pagadas)
        total_ordenes_no_pagadas = len(ordenes_no_pagadas)
        monto_total_pagado = sum(o.get('monto_pago', 0) for o in ordenes_pagadas)
        monto_total_pendiente = sum(o['monto_orden'] for o in ordenes_no_pagadas)
        
        # Separaciones por tipo
        ordenes_ventas = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'venta']
        ordenes_devoluciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'devolucion']
        ordenes_cancelaciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'cancelacion']
        
        # 7. Formatear estado para el frontend
        estado_formateado = liquidacion['estado']
        if estado_formateado == 'procesada':
            estado_formateado = 'Procesada'
        elif estado_formateado == 'pendiente':
            estado_formateado = 'Pendiente'
        elif estado_formateado == 'error':
            estado_formateado = 'Error'
        
        return {
            "liquidacion": {
                "id": liquidacion['id'],
                "retail": liquidacion['retail'],
                "numero_liquidacion": liquidacion['numero_liquidacion'] or 'N/A',
                "fecha_liquidacion": liquidacion['fecha_liquidacion'].isoformat() if liquidacion['fecha_liquidacion'] else None,
                "monto_total": float(liquidacion['monto_total']) if liquidacion['monto_total'] else 0,
                "cantidad_ordenes": liquidacion['cantidad_ordenes'] or 0,
                "estado": estado_formateado,
                "archivo_original": liquidacion['archivo_original'] or '',
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
                "monto_ventas": sum(o.get('monto_pago', 0) for o in ordenes_ventas),
                "monto_devoluciones": sum(o.get('monto_pago', 0) for o in ordenes_devoluciones),
                "monto_cancelaciones": sum(o.get('monto_pago', 0) for o in ordenes_cancelaciones),
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
        print(f"⚠️ Error de base de datos: {str(db_error)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(db_error)}")
    except Exception as e:
        print(f"⚠️ Error general: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

async def obtener_liquidacion_sin_ordenes(cursor, liquidacion_id):
    """Función auxiliar para obtener liquidación sin tabla ventas_retail"""
    try:
        query_liquidacion = """
        SELECT 
            l.id,
            l.cliente_id,
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
            l.estado,
            l.archivo_original,
            l.fecha_creacion,
            l.ordenes_procesadas,
            l.ordenes_actualizadas,
            l.ordenes_no_encontradas
        FROM liquidaciones l
        WHERE l.id = %s
        """
        
        cursor.execute(query_liquidacion, (liquidacion_id,))
        liquidacion = cursor.fetchone()
        
        if not liquidacion:
            raise HTTPException(status_code=404, detail="Liquidación no encontrada")
        
        return await obtener_liquidacion_sin_ordenes_simple(liquidacion)
        
    except Exception as e:
        print(f"Error en obtener_liquidacion_sin_ordenes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def obtener_liquidacion_sin_ordenes_simple(liquidacion):
    """Crear respuesta básica sin órdenes"""
    
    estado_formateado = liquidacion['estado']
    if estado_formateado == 'procesada':
        estado_formateado = 'Procesada'
    elif estado_formateado == 'pendiente':
        estado_formateado = 'Pendiente'
    elif estado_formateado == 'error':
        estado_formateado = 'Error'
    
    return {
        "liquidacion": {
            "id": liquidacion['id'],
            "retail": liquidacion['retail'],
            "numero_liquidacion": liquidacion['numero_liquidacion'] or 'N/A',
            "fecha_liquidacion": liquidacion['fecha_liquidacion'].isoformat() if liquidacion['fecha_liquidacion'] else None,
            "monto_total": float(liquidacion['monto_total']) if liquidacion['monto_total'] else 0,
            "cantidad_ordenes": liquidacion['cantidad_ordenes'] or 0,
            "estado": estado_formateado,
            "archivo_original": liquidacion['archivo_original'] or '',
            "fecha_creacion": liquidacion['fecha_creacion'].isoformat() if liquidacion['fecha_creacion'] else None,
            "ordenes_procesadas": liquidacion['ordenes_procesadas'] or 0,
            "ordenes_actualizadas": liquidacion['ordenes_actualizadas'] or 0,
            "ordenes_no_encontradas": liquidacion['ordenes_no_encontradas'] or 0
        },
        "estadisticas": {
            "total_ordenes_pagadas": 0,
            "total_ordenes_no_pagadas": 0,
            "monto_total_pagado": 0,
            "monto_total_pendiente": 0,
            "monto_ventas": 0,
            "monto_devoluciones": 0,
            "monto_cancelaciones": 0,
            "cantidad_ventas": 0,
            "cantidad_devoluciones": 0,
            "cantidad_cancelaciones": 0
        },
        "ordenes_pagadas": [],
        "ordenes_no_pagadas": [],
        "success": True
    }

async def obtener_ordenes_por_numero_liquidacion(cursor, liquidacion, liquidacion_id):
    """Función auxiliar para buscar órdenes por número de liquidación"""
    try:
        # Buscar órdenes que coincidan con el número de liquidación
        query_ordenes_fallback = """
        SELECT 
            v.id,
            v.numero_orden,
            v.fecha_venta AS fecha_orden,
            v.total AS monto_orden,
            v.monto_pago_liquidacion,
            v.tipo_liquidacion,
            v.fecha_liquidacion,
            v.numero_liquidacion,
            v.estado_liquidacion,
            v.estado_pago
        FROM ventas_retail v
        WHERE v.numero_liquidacion = %s AND v.cliente_id = %s
        ORDER BY v.fecha_venta DESC
        """
        
        cursor.execute(query_ordenes_fallback, (liquidacion['numero_liquidacion'], liquidacion['cliente_id']))
        ordenes = cursor.fetchall()
        
        print(f"📊 Órdenes encontradas por número: {len(ordenes)}")
        
        # Procesar igual que antes
        ordenes_pagadas = []
        ordenes_no_pagadas = []
        
        for orden in ordenes:
            registro = {
                'id': orden['id'],
                'numero_orden': orden['numero_orden'],
                'fecha_orden': orden['fecha_orden'].isoformat() if orden['fecha_orden'] else None,
                'monto_orden': float(orden['monto_orden']) if orden['monto_orden'] else 0,
                'tipo_liquidacion': orden['tipo_liquidacion'] or 'venta',
                'estado_pago': orden['estado_pago'] or 'pendiente'
            }
            
            if orden['estado_pago'] and orden['estado_pago'].lower() in ['pagado', 'pagada', 'cerrada']:
                registro['monto_pago'] = float(orden['monto_pago_liquidacion']) if orden['monto_pago_liquidacion'] else 0
                ordenes_pagadas.append(registro)
            else:
                ordenes_no_pagadas.append(registro)
        
        # Calcular estadísticas
        total_ordenes_pagadas = len(ordenes_pagadas)
        total_ordenes_no_pagadas = len(ordenes_no_pagadas)
        monto_total_pagado = sum(o.get('monto_pago', 0) for o in ordenes_pagadas)
        monto_total_pendiente = sum(o['monto_orden'] for o in ordenes_no_pagadas)
        
        ordenes_ventas = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'venta']
        ordenes_devoluciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'devolucion']
        ordenes_cancelaciones = [o for o in ordenes_pagadas if o['tipo_liquidacion'] == 'cancelacion']
        
        estado_formateado = liquidacion['estado']
        if estado_formateado == 'procesada':
            estado_formateado = 'Procesada'
        elif estado_formateado == 'pendiente':
            estado_formateado = 'Pendiente'
        elif estado_formateado == 'error':
            estado_formateado = 'Error'
        
        return {
            "liquidacion": {
                "id": liquidacion['id'],
                "retail": liquidacion['retail'],
                "numero_liquidacion": liquidacion['numero_liquidacion'] or 'N/A',
                "fecha_liquidacion": liquidacion['fecha_liquidacion'].isoformat() if liquidacion['fecha_liquidacion'] else None,
                "monto_total": float(liquidacion['monto_total']) if liquidacion['monto_total'] else 0,
                "cantidad_ordenes": liquidacion['cantidad_ordenes'] or 0,
                "estado": estado_formateado,
                "archivo_original": liquidacion['archivo_original'] or '',
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
                "monto_ventas": sum(o.get('monto_pago', 0) for o in ordenes_ventas),
                "monto_devoluciones": sum(o.get('monto_pago', 0) for o in ordenes_devoluciones),
                "monto_cancelaciones": sum(o.get('monto_pago', 0) for o in ordenes_cancelaciones),
                "cantidad_ventas": len(ordenes_ventas),
                "cantidad_devoluciones": len(ordenes_devoluciones),
                "cantidad_cancelaciones": len(ordenes_cancelaciones)
            },
            "ordenes_pagadas": ordenes_pagadas,
            "ordenes_no_pagadas": ordenes_no_pagadas,
            "success": True
        }
        
    except Exception as e:
        print(f"Error en obtener_ordenes_por_numero_liquidacion: {str(e)}")
        return await obtener_liquidacion_sin_ordenes_simple(liquidacion)
    

@router.get("/api/test/{liquidacion_id}")
async def test_liquidacion(liquidacion_id: int):
    """Endpoint de prueba para debuggear"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as count FROM liquidaciones WHERE id = %s", (liquidacion_id,))
        result = cursor.fetchone()
        
        return {"liquidacion_id": liquidacion_id, "exists": result['count'] > 0, "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}
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
    """
    Procesar liquidación de Cencosud de forma estructurada y limpia
    """
    print(f"🚀 Iniciando procesamiento de liquidación Cencosud: {nombre_archivo}")
    
    try:
        # 1. PROCESAR ARCHIVO EXCEL
        datos_excel = procesar_archivo_excel(contenido)
        if not datos_excel['success']:
            return crear_respuesta_error(datos_excel['error'], nombre_archivo)
        
        filas_procesadas = datos_excel['filas']
        print(f"📊 {len(filas_procesadas)} filas procesadas del Excel")
        
        # 2. ESTABLECER CONEXIÓN A BD
        conn, cursor = conectar_base_datos()
        if not conn:
            return crear_respuesta_error("Error conectando a base de datos", nombre_archivo)
        
        try:
            # 3. SEPARAR ÓRDENES VÁLIDAS Y NO ENCONTRADAS
            clasificacion = clasificar_ordenes(cursor, filas_procesadas)
            ordenes_validas = clasificacion['validas']
            ordenes_no_encontradas = clasificacion['no_encontradas']
            
            print(f"✅ {len(ordenes_validas)} órdenes encontradas")
            print(f"⚠️ {len(ordenes_no_encontradas)} órdenes no encontradas")
            
            # 4. CREAR REGISTRO DE LIQUIDACIÓN
            liquidacion_info = crear_liquidacion_master(
                cursor, filas_procesadas, ordenes_validas, ordenes_no_encontradas, 
                numero_liquidacion, nombre_archivo
            )
            
            if not liquidacion_info['success']:
                return crear_respuesta_error(liquidacion_info['error'], nombre_archivo)
            
            liquidacion_id = liquidacion_info['id']
            print(f"💾 Liquidación creada con ID: {liquidacion_id}")
            
            # 5. ACTUALIZAR ÓRDENES VÁLIDAS
            resultado_actualizacion = actualizar_ordenes_retail(cursor, ordenes_validas, liquidacion_id)
            
            # 6. GUARDAR ÓRDENES PENDIENTES
            resultado_pendientes = guardar_ordenes_pendientes(cursor, ordenes_no_encontradas, liquidacion_id)
            
            # 7. CONFIRMAR TRANSACCIÓN
            conn.commit()
            print("✅ Transacción confirmada")
            
            # 8. CREAR RESPUESTA FINAL
            return crear_respuesta_exitosa(
                liquidacion_info, resultado_actualizacion, resultado_pendientes, 
                nombre_archivo, filas_procesadas, ordenes_no_encontradas
            )
            
        except Exception as e:
            conn.rollback()
            print(f"🔄 Transacción revertida: {str(e)}")
            raise e
            
        finally:
            cerrar_conexion_bd(cursor, conn)
            
    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        return crear_respuesta_error(str(e), nombre_archivo)


def procesar_archivo_excel(contenido: bytes):
    """
    Procesar y validar archivo Excel de Cencosud
    """
    try:
        print("📖 Leyendo archivo Excel...")
        
        # Leer Excel
        excel_file = pd.ExcelFile(BytesIO(contenido))
        hoja = obtener_hoja_transacciones(excel_file)
        
        df = pd.read_excel(
            BytesIO(contenido), 
            sheet_name=hoja,
            na_values=['', 'nan', 'NaN', 'null', None],
            keep_default_na=True,
            dtype=str
        )
        
        print(f"📋 Leídas {len(df)} filas, {len(df.columns)} columnas")
        
        # Validar y mapear columnas
        columnas_mapeadas = mapear_columnas_cencosud(df)
        if not columnas_mapeadas['success']:
            return {"success": False, "error": columnas_mapeadas['error']}
        
        # Procesar filas
        filas_procesadas = procesar_filas_excel(df, columnas_mapeadas['mapeo'])
        
        return {
            "success": True,
            "filas": filas_procesadas,
            "total_filas": len(filas_procesadas)
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error procesando Excel: {str(e)}"}


def obtener_hoja_transacciones(excel_file):
    """Buscar la hoja de transacciones en el Excel"""
    hojas = excel_file.sheet_names
    
    for hoja in hojas:
        if 'transacciones' in hoja.lower() or 'transaccion' in hoja.lower():
            print(f"📊 Usando hoja: {hoja}")
            return hoja
    
    print(f"⚠️ Hoja 'transacciones' no encontrada, usando: {hojas[0]}")
    return hojas[0]


def mapear_columnas_cencosud(df):
    """Mapear columnas del Excel a nombres estándar"""
    df.columns = df.columns.str.strip().str.lower()
    
    columnas_requeridas = {
        'nro_suborden': ['nro suborden', 'número orden', 'numero orden', 'nro orden', 'orden', 'suborden'],
        'tipo': ['tipo', 'tipo liquidacion', 'tipo_liquidacion'],
        'monto': ['monto a pagar', 'monto pagar', 'monto', 'valor'],
        'fecha': ['fecha liq.factura', 'fecha liquidacion', 'fecha liq', 'fecha'],
        'numero_liq': ['número liq.factura', 'numero liq.factura', 'nro liquidacion'],
        'solicitud': ['nro solicitud liq.factura', 'solicitud', 'nro solicitud'],
        'estado': ['estado de liq.factura', 'estado liquidacion', 'estado']
    }
    
    mapeo = {}
    for col_std, variaciones in columnas_requeridas.items():
        encontrada = None
        for var in variaciones:
            if var in df.columns:
                encontrada = var
                break
        
        if encontrada:
            mapeo[col_std] = encontrada
            print(f"✅ {col_std} → {encontrada}")
        else:
            return {
                "success": False, 
                "error": f"Columna '{col_std}' no encontrada. Disponibles: {list(df.columns)}"
            }
    
    return {"success": True, "mapeo": mapeo}


def procesar_filas_excel(df, mapeo_columnas):
    """Procesar cada fila del Excel y limpiar datos"""
    filas_validas = []
    
    # Renombrar columnas
    df_renamed = df.rename(columns={v: k for k, v in mapeo_columnas.items()})
    
    for index, row in df_renamed.iterrows():
        try:
            fila_procesada = procesar_fila_individual(row, index)
            if fila_procesada:
                filas_validas.append(fila_procesada)
                
        except Exception as e:
            print(f"⚠️ Error fila {index + 2}: {str(e)}")
            continue
    
    return filas_validas


def procesar_fila_individual(row, index):
    """Procesar una fila individual del Excel"""
    
    # Extraer número de suborden
    numero_suborden = limpiar_campo(row.get('nro_suborden', ''))
    if not numero_suborden:
        return None
    
    # Procesar monto
    monto = procesar_monto(row.get('monto', 0))
    
    # Procesar fecha
    fecha = procesar_fecha(row.get('fecha'))
    
    # Otros campos
    fila_data = {
        'numero_suborden': numero_suborden,
        'tipo': limpiar_campo(row.get('tipo', 'venta')),
        'monto_pago': monto,
        'fecha_liquidacion': fecha,
        'numero_liquidacion_fila': limpiar_campo(row.get('numero_liq', '')),
        'nro_solicitud': limpiar_campo(row.get('solicitud', '')),
        'estado_liquidacion_excel': limpiar_campo(row.get('estado', 'pendiente')),
        'fila_excel': index + 2
    }
    
    print(f"✅ Fila {index + 2}: Suborden {numero_suborden}")
    return fila_data


def limpiar_campo(valor):
    """Limpiar campos de texto"""
    if pd.isna(valor) or str(valor).strip() in ['nan', 'NaN', '', 'None']:
        return ''
    return str(valor).strip()


def procesar_monto(valor_monto):
    """Procesar y validar montos"""
    try:
        if pd.isna(valor_monto) or str(valor_monto).strip() in ['nan', 'NaN', '', 'None']:
            return 0.0
        return float(str(valor_monto).replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


def procesar_fecha(valor_fecha):
    """Procesar fechas de forma segura"""
    if pd.isna(valor_fecha) or str(valor_fecha).strip() in ['nan', 'NaN', '', 'None']:
        return None
    
    try:
        if isinstance(valor_fecha, str):
            return pd.to_datetime(valor_fecha).date()
        else:
            return valor_fecha.date() if hasattr(valor_fecha, 'date') else None
    except:
        return None


def conectar_base_datos():
    """Establecer conexión a la base de datos"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        conn.autocommit = False
        
        # Crear tablas si no existen
        crear_tabla_liquidaciones(cursor)
        crear_tabla_ordenes_pendientes(cursor)
        
        return conn, cursor
        
    except Exception as e:
        print(f"❌ Error conectando BD: {str(e)}")
        return None, None


def clasificar_ordenes(cursor, filas_procesadas):
    """Clasificar órdenes en válidas y no encontradas"""
    CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
    
    ordenes_validas = []
    ordenes_no_encontradas = []
    
    for fila_data in filas_procesadas:
        numero_suborden = fila_data['numero_suborden']
        
        # Buscar en BD
        cursor.execute("""
            SELECT id, numero_orden 
            FROM ventas_retail 
            WHERE numero_orden = %s AND cliente_id = %s
        """, (numero_suborden, CLIENTE_CENCOSUD_ID))
        
        venta_encontrada = cursor.fetchone()
        
        if venta_encontrada:
            fila_data['venta_id'] = venta_encontrada['id']
            ordenes_validas.append(fila_data)
            print(f"✅ Orden {numero_suborden} encontrada (ID: {venta_encontrada['id']})")
        else:
            ordenes_no_encontradas.append(fila_data)
            print(f"⚠️ Orden {numero_suborden} no encontrada")
    
    return {
        'validas': ordenes_validas,
        'no_encontradas': ordenes_no_encontradas
    }


def crear_liquidacion_master(cursor, filas_procesadas, ordenes_validas, ordenes_no_encontradas, numero_liquidacion, nombre_archivo):
    """Crear el registro maestro de liquidación"""
    try:
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
        
        # Calcular totales
        monto_total = sum(fila['monto_pago'] for fila in filas_procesadas)
        fecha_liquidacion = next((f['fecha_liquidacion'] for f in filas_procesadas if f['fecha_liquidacion']), None)
        
        # Determinar número de liquidación
        numero_liquidacion_final = (
            numero_liquidacion or 
            next((f['numero_liquidacion_fila'] for f in filas_procesadas if f['numero_liquidacion_fila']), None) or
            f"LIQ-CEN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        
        # Determinar estado
        if len(ordenes_no_encontradas) == 0:
            estado = 'procesada'
        elif len(ordenes_validas) == 0:
            estado = 'error'
        else:
            estado = 'procesada'
        
        # Insertar liquidación
        query = """
        INSERT INTO liquidaciones (
            cliente_id, numero_liquidacion, fecha_liquidacion, 
            monto_total, cantidad_ordenes, estado, archivo_original,
            ordenes_procesadas, ordenes_actualizadas, ordenes_no_encontradas,
            fecha_creacion
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        valores = (
            CLIENTE_CENCOSUD_ID,
            numero_liquidacion_final,
            fecha_liquidacion,
            monto_total,
            len(filas_procesadas),
            estado,
            nombre_archivo,
            len(filas_procesadas),
            len(ordenes_validas),
            len(ordenes_no_encontradas)
        )
        
        cursor.execute(query, valores)
        liquidacion_id = cursor.lastrowid
        
        print(f"💾 Liquidación {liquidacion_id} creada: {numero_liquidacion_final}")
        
        return {
            'success': True,
            'id': liquidacion_id,
            'numero': numero_liquidacion_final,
            'monto_total': monto_total,
            'fecha': fecha_liquidacion,
            'estado': estado
        }
        
    except Exception as e:
        return {'success': False, 'error': f"Error creando liquidación: {str(e)}"}


def actualizar_ordenes_retail(cursor, ordenes_validas, liquidacion_id):
    """Actualizar órdenes en ventas_retail usando UPDATE por ID"""
    ordenes_actualizadas = 0
    errores_detallados = []
    
    print(f"🔧 Actualizando {len(ordenes_validas)} órdenes en ventas_retail")
    
    # Verificar primero que la tabla ventas_retail esté accesible
    verificacion_tabla = verificar_tabla_ventas_retail(cursor)
    if not verificacion_tabla['accessible']:
        error_critico = f"❌ PROBLEMA CRÍTICO: {verificacion_tabla['error']}"
        print(error_critico)
        return {
            'actualizadas': 0,
            'errores': [error_critico],
            'total': len(ordenes_validas),
            'problema_tabla': True,
            'detalle_problema': verificacion_tabla['error']
        }
    
    for orden in ordenes_validas:
        try:
            resultado = actualizar_orden_individual(cursor, orden, liquidacion_id)
            if resultado['success']:
                ordenes_actualizadas += 1
                print(f"✅ Orden {orden['numero_suborden']} actualizada")
            else:
                error_detallado = f"❌ PROBLEMA AL ACTUALIZAR ventas_retail - Orden {orden['numero_suborden']}: {resultado['error']}"
                errores_detallados.append(error_detallado)
                print(error_detallado)
                
        except Exception as e:
            error_detallado = f"❌ PROBLEMA AL ACTUALIZAR ventas_retail - Orden {orden['numero_suborden']}: {str(e)}"
            errores_detallados.append(error_detallado)
            print(error_detallado)
    
    # Si no se actualizó ninguna orden, generar mensaje específico
    if ordenes_actualizadas == 0 and len(ordenes_validas) > 0:
        problema_general = "❌ PROBLEMA CRÍTICO: No se pudo actualizar NINGUNA orden en ventas_retail"
        print(problema_general)
        errores_detallados.insert(0, problema_general)
        
        return {
            'actualizadas': 0,
            'errores': errores_detallados,
            'total': len(ordenes_validas),
            'problema_tabla': True,
            'detalle_problema': "Todas las actualizaciones de ventas_retail fallaron"
        }
    
    return {
        'actualizadas': ordenes_actualizadas,
        'errores': errores_detallados,
        'total': len(ordenes_validas),
        'problema_tabla': False
    }


def verificar_tabla_ventas_retail(cursor):
    """Verificar que la tabla ventas_retail esté accesible y tenga las columnas necesarias"""
    try:
        # 1. Verificar que la tabla existe
        cursor.execute("SHOW TABLES LIKE 'ventas_retail'")
        tabla_existe = cursor.fetchone()
        
        if not tabla_existe:
            return {
                'accessible': False,
                'error': "La tabla ventas_retail no existe en la base de datos"
            }
        
        # 2. Verificar columnas necesarias
        cursor.execute("DESCRIBE ventas_retail")
        columnas_existentes = [col['Field'] for col in cursor.fetchall()]
        
        columnas_requeridas = [
            'id', 'liquidacion_id', 'monto_pago_liquidacion', 'tipo_liquidacion',
            'fecha_liquidacion', 'numero_liquidacion', 'estado_liquidacion', 'estado_pago'
        ]
        
        columnas_faltantes = [col for col in columnas_requeridas if col not in columnas_existentes]
        
        if columnas_faltantes:
            return {
                'accessible': False,
                'error': f"Columnas faltantes en ventas_retail: {', '.join(columnas_faltantes)}"
            }
        
        # 3. Verificar permisos de escritura (hacer un UPDATE de prueba)
        cursor.execute("SELECT id FROM ventas_retail LIMIT 1")
        test_record = cursor.fetchone()
        
        if test_record:
            # Hacer UPDATE de prueba sin cambiar nada
            cursor.execute("UPDATE ventas_retail SET id = id WHERE id = %s", (test_record['id'],))
            if cursor.rowcount >= 0:  # >= 0 porque puede ser 0 si no hay cambios
                print("✅ Tabla ventas_retail accesible y con permisos de escritura")
                return {'accessible': True, 'error': None}
            else:
                return {
                    'accessible': False,
                    'error': "Sin permisos de escritura en ventas_retail"
                }
        else:
            return {
                'accessible': False,
                'error': "Tabla ventas_retail existe pero está vacía"
            }
            
    except mysql.connector.Error as db_error:
        return {
            'accessible': False,
            'error': f"Error de base de datos al acceder ventas_retail: {str(db_error)}"
        }
    except Exception as e:
        return {
            'accessible': False,
            'error': f"Error verificando ventas_retail: {str(e)}"
        }


def actualizar_orden_individual(cursor, orden, liquidacion_id):
    """Actualizar una orden individual usando su ID"""
    try:
        # Mapear tipo
        tipo_map = {
            'venta': 'venta', 'ventas': 'venta',
            'devolución': 'devolucion', 'devolucion': 'devolucion', 'devoluciones': 'devolucion'
        }
        tipo_liquidacion = tipo_map.get(orden['tipo'].lower(), 'cancelacion')
        
        # Mapear estado (usar valores correctos del enum)
        estado_excel = orden['estado_liquidacion_excel'].lower()
        if estado_excel in ['pagada', 'pagado', 'cerrada', 'finalizada']:
            estado_liquidacion = 'procesada'
            estado_pago = 'pagada'  # Usar 'pagada' que existe en el enum
        else:
            estado_liquidacion = 'procesada'
            estado_pago = 'pagada'
        
        # UPDATE por ID (más confiable que por numero_orden)
        query = """
        UPDATE ventas_retail SET 
            monto_pago_liquidacion = %s,
            tipo_liquidacion = %s,
            fecha_liquidacion = %s,
            numero_liquidacion = %s,
            fecha_procesamiento_liquidacion = %s,
            estado_liquidacion = %s,
            estado_pago = %s,
            liquidacion_id = %s
        WHERE id = %s
        """
        
        valores = (
            orden['monto_pago'],
            tipo_liquidacion,
            orden['fecha_liquidacion'],
            orden['numero_liquidacion_fila'],
            orden['nro_solicitud'],
            estado_liquidacion,
            estado_pago,
            liquidacion_id,
            orden['venta_id']  # Usar ID en lugar de numero_orden
        )
        
        cursor.execute(query, valores)
        filas_afectadas = cursor.rowcount
        
        if filas_afectadas > 0:
            # Verificar que se guardó correctamente
            cursor.execute("SELECT liquidacion_id FROM ventas_retail WHERE id = %s", (orden['venta_id'],))
            verificacion = cursor.fetchone()
            
            if verificacion and verificacion['liquidacion_id'] == liquidacion_id:
                return {'success': True}
            else:
                return {'success': False, 'error': 'liquidacion_id no se guardó correctamente'}
        else:
            return {'success': False, 'error': 'UPDATE no afectó ninguna fila'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


def guardar_ordenes_pendientes(cursor, ordenes_no_encontradas, liquidacion_id):
    """Guardar órdenes no encontradas como pendientes"""
    if not ordenes_no_encontradas:
        return {'guardadas': 0, 'errores': []}
    
    CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
    ordenes_guardadas = 0
    errores = []
    
    print(f"📝 Guardando {len(ordenes_no_encontradas)} órdenes como pendientes")
    
    for orden in ordenes_no_encontradas:
        try:
            # Mapear tipo
            tipo_map = {
                'venta': 'venta', 'ventas': 'venta',
                'devolución': 'devolucion', 'devolucion': 'devolucion'
            }
            tipo_liquidacion = tipo_map.get(orden['tipo'].lower(), 'cancelacion')
            
            query = """
            INSERT INTO ordenes_liquidacion_pendientes (
                liquidacion_id, numero_orden, monto_pago, tipo_liquidacion,
                fecha_liquidacion, numero_liquidacion, fecha_procesamiento_liquidacion,
                estado_liquidacion_excel, cliente_id, fila_excel, data_completa,
                estado, fecha_creacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', NOW())
            """
            
            valores = (
                liquidacion_id,
                orden['numero_suborden'],
                orden['monto_pago'],
                tipo_liquidacion,
                orden['fecha_liquidacion'],
                orden['numero_liquidacion_fila'],
                orden['nro_solicitud'],
                orden['estado_liquidacion_excel'],
                CLIENTE_CENCOSUD_ID,
                orden['fila_excel'],
                json.dumps(orden)
            )
            
            cursor.execute(query, valores)
            ordenes_guardadas += 1
            
        except Exception as e:
            errores.append(f"Orden {orden['numero_suborden']}: {str(e)}")
    
    return {'guardadas': ordenes_guardadas, 'errores': errores}


def crear_respuesta_exitosa(liquidacion_info, resultado_actualizacion, resultado_pendientes, nombre_archivo, filas_procesadas, ordenes_no_encontradas):
    """Crear respuesta de éxito"""
    
    # Verificación final
    ordenes_con_liquidacion_id = verificar_ordenes_actualizadas(liquidacion_info['id'])
    
    # Determinar mensaje según si hubo problemas con ventas_retail
    mensaje_base = "Liquidación de Cencosud procesada exitosamente"
    
    if resultado_actualizacion.get('problema_tabla', False):
        mensaje_base = f"❌ PROBLEMAS AL ACTUALIZAR ventas_retail: {resultado_actualizacion.get('detalle_problema', 'Error desconocido')}"
    elif resultado_actualizacion['actualizadas'] == 0 and len(filas_procesadas) > 0:
        mensaje_base = "❌ PROBLEMAS AL ACTUALIZAR ventas_retail: No se pudo actualizar ninguna orden en la tabla"
    elif resultado_pendientes['guardadas'] > 0:
        mensaje_base = f"Liquidación procesada: {resultado_actualizacion['actualizadas']} órdenes actualizadas, {resultado_pendientes['guardadas']} órdenes guardadas como pendientes"
    
    # Determinar si el proceso fue exitoso o tuvo problemas críticos
    success_status = True
    if resultado_actualizacion.get('problema_tabla', False) or resultado_actualizacion['actualizadas'] == 0:
        success_status = False
    
    respuesta = {
        "success": success_status,
        "message": mensaje_base,
        "retail": "Cencosud",
        "archivo": nombre_archivo,
        "liquidacion_id": liquidacion_info['id'],
        "numero_liquidacion": liquidacion_info['numero'],
        "ordenes_procesadas": len(filas_procesadas),
        "ordenes_actualizadas": resultado_actualizacion['actualizadas'],
        "ordenes_no_encontradas": resultado_pendientes['guardadas'],
        "ordenes_con_liquidacion_id_verificadas": ordenes_con_liquidacion_id,
        "monto_total": liquidacion_info['monto_total'],
        "fecha_liquidacion": liquidacion_info['fecha'].isoformat() if liquidacion_info['fecha'] else None,
        "fecha_procesamiento": datetime.now().isoformat(),
        "errores": resultado_actualizacion['errores'][:10]
    }
    
    # Agregar información específica sobre problemas con ventas_retail
    if resultado_actualizacion.get('problema_tabla', False):
        respuesta["problema_ventas_retail"] = True
        respuesta["detalle_problema_ventas_retail"] = resultado_actualizacion.get('detalle_problema', 'Error desconocido')
    else:
        respuesta["problema_ventas_retail"] = False
    
    # Agregar detalles de órdenes pendientes si las hay
    if resultado_pendientes['guardadas'] > 0:
        respuesta["detalle_ordenes_faltantes"] = [
            {
                "numero_orden": fila['numero_suborden'],
                "fila_excel": fila['fila_excel'],
                "monto": fila['monto_pago']
            }
            for fila in ordenes_no_encontradas[:20]  # Máximo 20 para el response
        ]
    
    print(f"\n🎯 RESUMEN FINAL:")
    if not success_status:
        print(f"   ❌ PROBLEMAS CON ventas_retail: {resultado_actualizacion.get('detalle_problema', 'Error desconocido')}")
    print(f"   ✅ Órdenes actualizadas: {resultado_actualizacion['actualizadas']}")
    print(f"   ⚠️ Órdenes pendientes: {resultado_pendientes['guardadas']}")
    print(f"   🔍 Verificadas con liquidacion_id: {ordenes_con_liquidacion_id}")
    print(f"   💰 Monto total: ${liquidacion_info['monto_total']:,.2f}")
    
    if resultado_actualizacion['errores']:
        print(f"   🚨 Errores de actualización:")
        for error in resultado_actualizacion['errores'][:5]:
            print(f"      - {error}")
    
    return respuesta


def verificar_ordenes_actualizadas(liquidacion_id):
    """Verificar cuántas órdenes tienen el liquidacion_id asignado"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM ventas_retail WHERE liquidacion_id = %s", (liquidacion_id,))
        resultado = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return resultado['total'] if resultado else 0
        
    except Exception as e:
        print(f"⚠️ Error verificando órdenes: {str(e)}")
        return 0


def crear_respuesta_error(mensaje_error, nombre_archivo):
    """Crear respuesta de error estandarizada"""
    return {
        "success": False,
        "message": f"Error procesando archivo de Cencosud: {mensaje_error}",
        "retail": "Cencosud",
        "archivo": nombre_archivo,
        "liquidacion_id": None,
        "numero_liquidacion": None,
        "ordenes_procesadas": 0,
        "ordenes_actualizadas": 0,
        "ordenes_no_encontradas": 0,
        "ordenes_con_liquidacion_id_verificadas": 0,
        "monto_total": 0,
        "errores": [mensaje_error]
    }


def cerrar_conexion_bd(cursor, conn):
    """Cerrar conexiones de base de datos de forma segura"""
    try:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("🔌 Conexión BD cerrada")
    except Exception as e:
        print(f"⚠️ Error cerrando BD: {str(e)}")