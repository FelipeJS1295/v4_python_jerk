from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from db import conectar_mysql
from typing import Dict, List
import pandas as pd
import logging
from datetime import datetime
import io
from collections import defaultdict

# Configurar logging
logger = logging.getLogger(__name__)

# Crear el router
router = APIRouter(prefix="/liquidaciones/walmart", tags=["liquidaciones-walmart"])

@router.post("/procesar")
async def procesar_liquidacion_walmart(archivo: UploadFile = File(...)):
    """
    Procesar archivo CSV de liquidación de Walmart
    """
    connection = None
    try:
        # Validar archivo
        if not archivo.filename.endswith(('.csv')):
            raise HTTPException(status_code=400, detail="El archivo debe ser un CSV (.csv)")
        
        # Leer archivo CSV
        logger.info(f"Procesando archivo de Walmart: {archivo.filename}")
        
        contents = await archivo.read()
        # Intentar con diferentes encodings
        try:
            csv_content = contents.decode('utf-8')
        except UnicodeDecodeError:
            csv_content = contents.decode('latin-1')
        
        # Leer CSV con pandas usando delimitador correcto
        df = pd.read_csv(io.StringIO(csv_content), delimiter=';')
        
        # Validar columnas requeridas
        columnas_requeridas = ['Orden', 'Nº Liq.', 'Fecha Fin Liq.', 'Estado', 'Precio Item', 'Cargo Comision']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            raise HTTPException(
                status_code=400, 
                detail=f"Columnas faltantes en el CSV: {', '.join(columnas_faltantes)}"
            )
        
        # Filtrar solo filas con datos válidos
        df_valido = df.dropna(subset=['Orden', 'Nº Liq.'])
        
        if df_valido.empty:
            raise HTTPException(status_code=400, detail="No se encontraron registros válidos en el archivo")
        
        logger.info(f"Registros válidos encontrados: {len(df_valido)}")
        
        # Agrupar por orden para procesar múltiples filas por orden
        ordenes_agrupadas = defaultdict(list)
        
        for index, row in df_valido.iterrows():
            orden = str(row['Orden']).strip()
            ordenes_agrupadas[orden].append(row)
        
        logger.info(f"Órdenes únicas encontradas: {len(ordenes_agrupadas)}")
        
        # Conectar a la base de datos
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Procesar cada orden
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        ordenes_fallidas = 0
        errores = []
        
        for numero_orden, filas_orden in ordenes_agrupadas.items():
            try:
                # Tomar datos comunes de la primera fila
                primera_fila = filas_orden[0]
                numero_liquidacion = str(primera_fila['Nº Liq.']).strip()
                fecha_fin_liquidacion = primera_fila['Fecha Fin Liq.']
                
                # Convertir fecha
                fecha_liquidacion = None
                if pd.notna(fecha_fin_liquidacion):
                    try:
                        # Formato esperado: dd-mm-yyyy
                        fecha_liquidacion = pd.to_datetime(fecha_fin_liquidacion, format='%d-%m-%Y').date()
                    except:
                        try:
                            fecha_liquidacion = pd.to_datetime(fecha_fin_liquidacion).date()
                        except:
                            fecha_liquidacion = None
                
                # Calcular monto líquido sumando todas las filas de la orden
                monto_total = 0
                estados_orden = []
                
                for fila in filas_orden:
                    precio_item = float(fila['Precio Item']) if pd.notna(fila['Precio Item']) else 0
                    cargo_comision = float(fila['Cargo Comision']) if pd.notna(fila['Cargo Comision']) else 0
                    estado = str(fila['Estado']).strip()
                    
                    monto_total += precio_item + cargo_comision
                    estados_orden.append(estado)
                
                # Determinar estado final de la orden
                estado_pago = determinar_estado_walmart(estados_orden)
                
                logger.info(f"Procesando orden {numero_orden}: monto={monto_total}, estado={estado_pago}, filas={len(filas_orden)}")
                
                # Buscar la orden en ventas_retail
                buscar_query = """
                    SELECT id, numero_orden 
                    FROM ventas_retail 
                    WHERE numero_orden = %s
                """
                
                cursor.execute(buscar_query, (numero_orden,))
                orden_encontrada = cursor.fetchone()
                
                if orden_encontrada:
                    # Actualizar la orden
                    actualizar_query = """
                        UPDATE ventas_retail 
                        SET numero_liquidacion = %s,
                            fecha_pago_liquidacion = %s,
                            monto_liquido = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """
                    
                    cursor.execute(actualizar_query, (
                        numero_liquidacion,
                        fecha_liquidacion,
                        monto_total,
                        orden_encontrada['id']
                    ))
                    
                    if estado_pago == 'fallido':
                        ordenes_fallidas += 1
                    else:
                        ordenes_actualizadas += 1
                    
                    logger.info(f"Orden actualizada: {numero_orden} -> ID {orden_encontrada['id']} (Estado: {estado_pago})")
                    
                else:
                    ordenes_no_encontradas += 1
                    logger.warning(f"Orden no encontrada: {numero_orden}")
                    errores.append(f"Orden {numero_orden} no encontrada en la base de datos")
                
            except Exception as e:
                logger.error(f"Error procesando orden {numero_orden}: {str(e)}")
                errores.append(f"Error en orden {numero_orden}: {str(e)}")
                continue
        
        # Confirmar cambios
        connection.commit()
        
        # Preparar respuesta
        resultado = {
            "mensaje": "Liquidación de Walmart procesada exitosamente",
            "archivo_procesado": archivo.filename,
            "total_ordenes_procesadas": len(ordenes_agrupadas),
            "ordenes_actualizadas": ordenes_actualizadas,
            "ordenes_fallidas": ordenes_fallidas,
            "ordenes_no_encontradas": ordenes_no_encontradas,
            "total_filas_csv": len(df_valido),
            "errores": errores[:10],  # Mostrar solo los primeros 10 errores
            "fecha_procesamiento": datetime.now().isoformat()
        }
        
        logger.info(f"Procesamiento Walmart completado: {ordenes_actualizadas} actualizadas, {ordenes_fallidas} fallidas, {ordenes_no_encontradas} no encontradas")
        
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error procesando liquidación de Walmart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

def determinar_estado_walmart(estados: List[str]) -> str:
    """
    Determinar el estado final de una orden basado en los estados de todas sus filas
    
    Reglas:
    - Si todas las filas son "Enviado" -> pagado
    - Si alguna fila es "Devolucion" -> fallido
    - Otros casos -> fallido
    """
    estados_lower = [estado.lower() for estado in estados]
    
    # Si hay alguna devolución, es fallido
    if any('devolucion' in estado for estado in estados_lower):
        return 'fallido'
    
    # Si todas son enviado, es pagado
    if all('enviado' in estado for estado in estados_lower):
        return 'pagado'
    
    # Cualquier otro caso es fallido
    return 'fallido'

@router.get("/estado/{numero_liquidacion}")
async def consultar_estado_liquidacion_walmart(numero_liquidacion: str):
    """
    Consultar el estado de una liquidación específica de Walmart
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT 
                vr.id,
                vr.numero_orden,
                vr.producto,
                c.nombre as cliente_nombre,
                vr.numero_liquidacion,
                vr.fecha_pago_liquidacion,
                vr.monto_liquido,
                vr.precio_cliente,
                CASE 
                    WHEN vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NOT NULL THEN 'pagado'
                    WHEN vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NULL THEN 'pendiente'
                    ELSE 'fallido'
                END AS estado_pago
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.numero_liquidacion = %s
            ORDER BY vr.fecha_pago_liquidacion DESC
        """
        
        cursor.execute(query, (numero_liquidacion,))
        ordenes = cursor.fetchall()
        
        if not ordenes:
            raise HTTPException(status_code=404, detail="No se encontraron órdenes con esa liquidación")
        
        # Convertir fechas para JSON
        for orden in ordenes:
            if orden.get('fecha_pago_liquidacion'):
                orden['fecha_pago_liquidacion'] = orden['fecha_pago_liquidacion'].isoformat()
            if orden.get('monto_liquido'):
                orden['monto_liquido'] = float(orden['monto_liquido'])
        
        return {
            "numero_liquidacion": numero_liquidacion,
            "total_ordenes": len(ordenes),
            "ordenes": ordenes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consultando liquidación Walmart {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/reportes/detalle/{numero_liquidacion}")
async def reporte_detalle_liquidacion(numero_liquidacion: str):
    """
    Generar reporte detallado de una liquidación de Walmart
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Resumen de la liquidación
        resumen_query = """
            SELECT 
                COUNT(*) as total_ordenes,
                SUM(monto_liquido) as monto_total_liquidado,
                AVG(monto_liquido) as promedio_por_orden,
                MIN(fecha_pago_liquidacion) as fecha_procesamiento
            FROM ventas_retail
            WHERE numero_liquidacion = %s
        """
        
        cursor.execute(resumen_query, (numero_liquidacion,))
        resumen = cursor.fetchone()
        
        # Detalle por orden
        detalle_query = """
            SELECT 
                vr.numero_orden,
                vr.producto,
                c.nombre as cliente_nombre,
                vr.monto_liquido,
                vr.precio_cliente,
                vr.fecha_pago_liquidacion
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.numero_liquidacion = %s
            ORDER BY vr.numero_orden
        """
        
        cursor.execute(detalle_query, (numero_liquidacion,))
        detalle = cursor.fetchall()
        
        # Convertir fechas
        if resumen.get('fecha_procesamiento'):
            resumen['fecha_procesamiento'] = resumen['fecha_procesamiento'].isoformat()
        
        for orden in detalle:
            if orden.get('fecha_pago_liquidacion'):
                orden['fecha_pago_liquidacion'] = orden['fecha_pago_liquidacion'].isoformat()
            if orden.get('monto_liquido'):
                orden['monto_liquido'] = float(orden['monto_liquido'])
        
        return {
            "numero_liquidacion": numero_liquidacion,
            "resumen": resumen,
            "detalle_ordenes": detalle,
            "fecha_reporte": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generando reporte detalle Walmart {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/reportes/resumen")
async def generar_reporte_resumen_walmart():
    """
    Generar reporte resumen de liquidaciones de Walmart
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Estadísticas generales de Walmart
        stats_query = """
            SELECT 
                COUNT(*) as total_ordenes,
                SUM(CASE WHEN numero_liquidacion IS NOT NULL THEN 1 ELSE 0 END) as ordenes_con_liquidacion,
                SUM(CASE WHEN numero_liquidacion IS NULL THEN 1 ELSE 0 END) as ordenes_sin_liquidacion,
                COALESCE(SUM(monto_liquido), 0) as total_liquidado,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NULL THEN precio_cliente ELSE 0 END), 0) as total_pendiente,
                COUNT(DISTINCT numero_liquidacion) as liquidaciones_unicas,
                COALESCE(AVG(monto_liquido), 0) as promedio_liquidacion
            FROM ventas_retail
            WHERE cliente_id = (SELECT id FROM clientes WHERE nombre LIKE '%walmart%' LIMIT 1)
        """
        
        cursor.execute(stats_query)
        stats = cursor.fetchone()
        
        # Liquidaciones recientes de Walmart
        recientes_query = """
            SELECT 
                numero_liquidacion,
                fecha_pago_liquidacion,
                COUNT(*) as ordenes_en_liquidacion,
                SUM(monto_liquido) as monto_total
            FROM ventas_retail
            WHERE numero_liquidacion IS NOT NULL 
            AND cliente_id = (SELECT id FROM clientes WHERE nombre LIKE '%walmart%' LIMIT 1)
            GROUP BY numero_liquidacion, fecha_pago_liquidacion
            ORDER BY fecha_pago_liquidacion DESC
            LIMIT 10
        """
        
        cursor.execute(recientes_query)
        liquidaciones_recientes = cursor.fetchall()
        
        # Convertir fechas y montos
        for liquidacion in liquidaciones_recientes:
            if liquidacion.get('fecha_pago_liquidacion'):
                liquidacion['fecha_pago_liquidacion'] = liquidacion['fecha_pago_liquidacion'].isoformat()
            if liquidacion.get('monto_total'):
                liquidacion['monto_total'] = float(liquidacion['monto_total'])
        
        return {
            "cliente": "Walmart",
            "estadisticas": stats,
            "liquidaciones_recientes": liquidaciones_recientes,
            "fecha_reporte": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generando reporte de Walmart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()