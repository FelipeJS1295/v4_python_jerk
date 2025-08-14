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
    """Procesar liquidación específica de Cencosud con validación previa completa"""
    try:
        # Leer archivo Excel
        df = pd.read_excel(BytesIO(contenido), sheet_name='transacciones')
        
        # Validar columnas requeridas para Cencosud
        columnas_requeridas = [
            'número orden', 
            'tipo', 
            'monto a pagar', 
            'fecha liq.factura', 
            'número liq.factura',
            'nro solicitud liq.factura',
            'estado de liq.factura'
        ]
        
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            raise Exception(f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}")
        
        # Obtener información de la liquidación del Excel
        numero_liquidacion_excel = str(df['número liq.factura'].iloc[0]) if len(df) > 0 else None
        fecha_liquidacion = df['fecha liq.factura'].iloc[0] if len(df) > 0 else None
        
        # Usar el número proporcionado o el del Excel
        numero_liquidacion_final = numero_liquidacion or numero_liquidacion_excel
        
        conn = obtener_conexion_db()
        cursor = conn.cursor()
        
        # Configurar autocommit
        conn.autocommit = False
        
        # ID del cliente Cencosud
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
        
        try:
            # Asegurar que no hay transacciones pendientes
            try:
                conn.rollback()
            except:
                pass
            
            print(f"🔍 Iniciando validación de {len(df)} órdenes del Excel")
            
            # PASO 1: VALIDACIÓN PREVIA - Verificar que TODAS las órdenes existan
            ordenes_no_encontradas = []
            ordenes_validas = []
            
            for index, row in df.iterrows():
                try:
                    numero_orden_excel = str(row['número orden']).strip()
                    
                    # PARA CENCOSUD: Agregar '0' al final del número de orden del Excel
                    # porque en la BD terminan en 0 pero en el Excel vienen sin ese 0
                    numero_orden_bd = numero_orden_excel + '0'
                    
                    print(f"📋 Fila {index + 1}: Excel={numero_orden_excel} -> BD={numero_orden_bd}")
                    
                    # Buscar la orden en ventas_retail usando el número con '0' agregado
                    query_buscar = """
                    SELECT id, numero_orden FROM ventas_retail 
                    WHERE numero_orden = %s AND cliente_id = %s
                    """
                    
                    cursor.execute(query_buscar, (numero_orden_bd, CLIENTE_CENCOSUD_ID))
                    venta_encontrada = cursor.fetchone()
                    
                    if venta_encontrada:
                        ordenes_validas.append({
                            'numero_orden_excel': numero_orden_excel,  # Número original del Excel
                            'numero_orden_bd': numero_orden_bd,        # Número para buscar en BD
                            'venta_id': venta_encontrada[0],
                            'fila_excel': index + 1,
                            'data': row
                        })
                        print(f"✅ Orden {numero_orden_excel} encontrada en BD como {numero_orden_bd}")
                    else:
                        ordenes_no_encontradas.append({
                            'numero_orden': numero_orden_excel,
                            'fila_excel': index + 1
                        })
                        print(f"❌ Orden {numero_orden_excel} NO encontrada en BD (buscado como {numero_orden_bd})")
                        
                except Exception as e:
                    ordenes_no_encontradas.append({
                        'numero_orden': str(row.get('número orden', 'N/A')),
                        'fila_excel': index + 1,
                        'error': str(e)
                    })
            
            # Si hay órdenes no encontradas, DETENER el proceso
            if ordenes_no_encontradas:
                print(f"❌ Se encontraron {len(ordenes_no_encontradas)} órdenes que no existen en la base de datos")
                
                # Crear mensaje detallado de error
                mensaje_error = f"No se pudo procesar la liquidación. Se encontraron {len(ordenes_no_encontradas)} órdenes que no existen en la base de datos:"
                
                ordenes_faltantes_texto = []
                for orden in ordenes_no_encontradas[:10]:  # Mostrar máximo 10
                    ordenes_faltantes_texto.append(f"• Orden: {orden['numero_orden']} (Fila {orden['fila_excel']} del Excel)")
                
                if len(ordenes_no_encontradas) > 10:
                    ordenes_faltantes_texto.append(f"• ... y {len(ordenes_no_encontradas) - 10} órdenes más")
                
                return {
                    "success": False,
                    "message": mensaje_error,
                    "retail": "Cencosud",
                    "archivo": nombre_archivo,
                    "ordenes_procesadas": len(df),
                    "ordenes_actualizadas": 0,
                    "ordenes_no_encontradas": len(ordenes_no_encontradas),
                    "ordenes_con_error": 0,
                    "monto_total": 0,
                    "monto_ventas": 0,
                    "monto_devoluciones": 0,
                    "errores": ordenes_faltantes_texto,
                    "detalle_ordenes_faltantes": ordenes_no_encontradas  # Para el frontend
                }
            
            print(f"✅ Todas las órdenes ({len(ordenes_validas)}) existen en la base de datos. Procediendo con la actualización...")
            
            # PASO 2: PROCESAMIENTO - Todas las órdenes son válidas, proceder con las actualizaciones
            ordenes_actualizadas = 0
            monto_total = 0
            monto_ventas = 0
            monto_devoluciones = 0
            errores_procesamiento = []
            
            print("🔄 Iniciando actualizaciones de órdenes")
            
            for orden_data in ordenes_validas:
                try:
                    row = orden_data['data']
                    numero_orden_excel = orden_data['numero_orden_excel']  # Número del Excel
                    numero_orden_bd = orden_data['numero_orden_bd']        # Número para BD
                    
                    tipo = str(row['tipo']).strip()
                    monto_pago = float(row['monto a pagar']) if pd.notna(row['monto a pagar']) else 0
                    fecha_liquidacion_fila = row['fecha liq.factura'] if pd.notna(row['fecha liq.factura']) else None
                    numero_liquidacion_fila = str(row['número liq.factura']).strip() if pd.notna(row['número liq.factura']) else None
                    nro_solicitud = str(row['nro solicitud liq.factura']).strip() if pd.notna(row['nro solicitud liq.factura']) else None
                    estado_liquidacion_excel = str(row['estado de liq.factura']).strip() if pd.notna(row['estado de liq.factura']) else 'pendiente'
                    
                    print(f"🔄 Actualizando orden Excel:{numero_orden_excel} -> BD:{numero_orden_bd}")
                    
                    # Mapear tipo a enum
                    if tipo.lower() in ['venta', 'ventas']:
                        tipo_liquidacion = 'venta'
                        monto_ventas += monto_pago
                    elif tipo.lower() in ['devolución', 'devolucion', 'devoluciones']:
                        tipo_liquidacion = 'devolucion'
                        monto_devoluciones += monto_pago
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
                    
                    monto_total += monto_pago
                    
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
                        errores_procesamiento.append(f"Orden {numero_orden_excel} no se pudo actualizar")
                        print(f"⚠️ Orden {numero_orden_excel} no se pudo actualizar")
                    
                except Exception as e:
                    error_msg = f"Error actualizando orden {numero_orden_excel}: {str(e)}"
                    errores_procesamiento.append(error_msg)
                    print(f"❌ {error_msg}")
                    continue
            
            # Guardar registro de la liquidación procesada
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
                len(ordenes_validas),
                'procesada' if ordenes_actualizadas > 0 else 'error',
                nombre_archivo,
                len(ordenes_validas),
                ordenes_actualizadas,
                0  # ordenes_no_encontradas es 0 porque ya validamos
            )
            
            cursor.execute(query_liquidacion, valores_liquidacion)
            
            # Commit de la transacción
            try:
                conn.commit()
                print("✅ Transacción confirmada exitosamente")
            except Exception as commit_error:
                print(f"⚠️ Error en commit: {str(commit_error)}")
                conn.rollback()
                raise commit_error
            
            print(f"✅ Liquidación procesada exitosamente:")
            print(f"   - Órdenes procesadas: {len(ordenes_validas)}")
            print(f"   - Órdenes actualizadas: {ordenes_actualizadas}")
            print(f"   - Monto total: {monto_total}")
            
            return {
                "success": True,
                "message": "Liquidación de Cencosud procesada exitosamente",
                "retail": "Cencosud",
                "archivo": nombre_archivo,
                "numero_liquidacion": numero_liquidacion_final,
                "ordenes_procesadas": len(ordenes_validas),
                "ordenes_actualizadas": ordenes_actualizadas,
                "ordenes_no_encontradas": 0,
                "ordenes_con_error": len(errores_procesamiento),
                "monto_total": monto_total,
                "monto_ventas": monto_ventas,
                "monto_devoluciones": monto_devoluciones,
                "fecha_liquidacion": fecha_liquidacion.isoformat() if fecha_liquidacion else None,
                "fecha_procesamiento": datetime.now().isoformat(),
                "errores": errores_procesamiento[:10] if errores_procesamiento else []
            }
            
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
                cursor.close()
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
            "ordenes_con_error": 0,
            "monto_total": 0,
            "errores": [str(e)]
        }