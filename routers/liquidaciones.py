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
    try:
        # Verificar si existe la tabla liquidaciones
        try:
            conn = obtener_conexion_db()
            cursor = conn.cursor(dictionary=True)
            
            # Verificar si la tabla existe
            cursor.execute("SHOW TABLES LIKE 'liquidaciones'")
            tabla_existe = cursor.fetchone()
            
            if not tabla_existe:
                # Crear tabla si no existe
                crear_tabla_liquidaciones(cursor)
                conn.commit()
            
            # Construir query base
            query = """
            SELECT 
                l.id,
                COALESCE(c.nombre, 'Desconocido') as retail,
                l.numero_liquidacion,
                l.fecha_liquidacion,
                l.monto_total,
                l.cantidad_ordenes,
                l.estado,
                l.archivo_original,
                l.fecha_creacion
            FROM liquidaciones l
            LEFT JOIN clientes c ON l.cliente_id = c.id
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
                "SELECT l.id, COALESCE(c.nombre, 'Desconocido') as retail, l.numero_liquidacion, l.fecha_liquidacion, l.monto_total, l.cantidad_ordenes, l.estado, l.archivo_original, l.fecha_creacion",
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
            
        except mysql.connector.Error as db_error:
            print(f"Error de base de datos: {str(db_error)}")
            return {
                "liquidaciones": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "error": "Error de base de datos"
            }
        
    except Exception as e:
        print(f"Error en obtener_liquidaciones: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al obtener liquidaciones: {str(e)}")

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
    try:
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
                COALESCE(c.nombre, 'Desconocido') as retail,
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
            LEFT JOIN clientes c ON v.cliente_id = c.id
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
                "SELECT v.numero_orden, COALESCE(c.nombre, 'Desconocido') as retail, v.fecha_venta as fecha_orden, v.total as monto, CASE WHEN v.estado_liquidacion = 'cerrada' THEN 'Pagado' WHEN v.estado_liquidacion = 'pendiente' THEN 'Pendiente' ELSE 'Sin procesar' END as estado_pago, v.fecha_liquidacion as fecha_pago, v.numero_liquidacion",
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
            COALESCE(c.nombre, 'Desconocido') as retail,
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
        LEFT JOIN clientes c ON v.cliente_id = c.id
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
        
        cursor.close()
        conn.close()
        
        return orden
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en obtener_detalle_orden: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de orden: {str(e)}")

@router.get("/api/estadisticas")
async def obtener_estadisticas_liquidaciones():
    """Obtener estadísticas generales de liquidaciones"""
    try:
        conn = obtener_conexion_db()
        cursor = conn.cursor(dictionary=True)
        
        # Estadísticas básicas si las tablas existen
        stats_liquidaciones = {"total_liquidaciones": 0, "monto_total_liquidado": 0, "total_ordenes_liquidadas": 0}
        stats_por_retail = []
        ordenes_pendientes = []
        
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
        
        cursor.close()
        conn.close()
        
        return {
            "liquidaciones": stats_liquidaciones,
            "por_retail": stats_por_retail,
            "ordenes_pendientes": ordenes_pendientes
        }
        
    except Exception as e:
        print(f"Error en obtener_estadisticas_liquidaciones: {str(e)}")
        return {
            "liquidaciones": {"total_liquidaciones": 0, "monto_total_liquidado": 0, "total_ordenes_liquidadas": 0},
            "por_retail": [],
            "ordenes_pendientes": []
        }

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
        
        # ID del cliente Cencosud
        CLIENTE_CENCOSUD_ID = RETAIL_CONFIG["cencosud"]["cliente_id"]
        
        try:
            print(f"🔍 Iniciando validación de {len(df)} órdenes del Excel")
            
            # PASO 1: VALIDACIÓN PREVIA - Verificar que TODAS las órdenes existan
            ordenes_no_encontradas = []
            ordenes_validas = []
            
            for index, row in df.iterrows():
                try:
                    numero_orden = str(row['número orden']).strip()
                    
                    # Buscar la orden en ventas_retail
                    query_buscar = """
                    SELECT id, numero_orden FROM ventas_retail 
                    WHERE numero_orden = %s AND cliente_id = %s
                    """
                    
                    cursor.execute(query_buscar, (numero_orden, CLIENTE_CENCOSUD_ID))
                    venta_encontrada = cursor.fetchone()
                    
                    if venta_encontrada:
                        ordenes_validas.append({
                            'numero_orden': numero_orden,
                            'venta_id': venta_encontrada[0],
                            'fila_excel': index + 1,
                            'data': row
                        })
                        print(f"✅ Orden {numero_orden} encontrada en BD")
                    else:
                        ordenes_no_encontradas.append({
                            'numero_orden': numero_orden,
                            'fila_excel': index + 1
                        })
                        print(f"❌ Orden {numero_orden} NO encontrada en BD")
                        
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
            
            # Iniciar transacción para las actualizaciones
            conn.start_transaction()
            
            for orden_data in ordenes_validas:
                try:
                    row = orden_data['data']
                    numero_orden = orden_data['numero_orden']
                    
                    tipo = str(row['tipo']).strip()
                    monto_pago = float(row['monto a pagar']) if pd.notna(row['monto a pagar']) else 0
                    fecha_liquidacion_fila = row['fecha liq.factura'] if pd.notna(row['fecha liq.factura']) else None
                    numero_liquidacion_fila = str(row['número liq.factura']).strip() if pd.notna(row['número liq.factura']) else None
                    nro_solicitud = str(row['nro solicitud liq.factura']).strip() if pd.notna(row['nro solicitud liq.factura']) else None
                    estado_liquidacion_excel = str(row['estado de liq.factura']).strip() if pd.notna(row['estado de liq.factura']) else 'pendiente'
                    
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
                    
                    # Actualizar la orden existente con los datos de liquidación
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
                        numero_orden,                  # WHERE numero_orden
                        CLIENTE_CENCOSUD_ID           # WHERE cliente_id
                    )
                    
                    cursor.execute(query_update, valores)
                    
                    if cursor.rowcount > 0:
                        ordenes_actualizadas += 1
                        print(f"✅ Orden {numero_orden} actualizada exitosamente")
                    else:
                        errores_procesamiento.append(f"Orden {numero_orden} no se pudo actualizar (sin cambios)")
                        print(f"⚠️ Orden {numero_orden} no se pudo actualizar")
                    
                except Exception as e:
                    error_msg = f"Error actualizando orden {numero_orden}: {str(e)}"
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
            conn.commit()
            
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
            conn.rollback()
            print(f"❌ Error en transacción: {str(e)}")
            raise e
        finally:
            cursor.close()
            conn.close()
        
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