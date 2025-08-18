from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from db import conectar_mysql
from typing import Dict, List
import pandas as pd
import logging
from datetime import datetime
import io

# Configurar logging
logger = logging.getLogger(__name__)

# Crear el router
router = APIRouter(prefix="/liquidaciones/cencosud", tags=["liquidaciones-cencosud"])

@router.post("/procesar")
async def procesar_liquidacion_cencosud(archivo: UploadFile = File(...)):
    """
    Procesar archivo Excel de liquidación de Cencosud
    """
    connection = None
    try:
        # Validar archivo
        if not archivo.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx o .xls)")
        
        # Leer archivo Excel
        logger.info(f"Procesando archivo de Cencosud: {archivo.filename}")
        
        contents = await archivo.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Validar columnas requeridas
        columnas_requeridas = ['nro suborden', 'monto a pagar', 'número liq.factura', 'fecha liq.factura']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            raise HTTPException(
                status_code=400, 
                detail=f"Columnas faltantes en el Excel: {', '.join(columnas_faltantes)}"
            )
        
        # Filtrar solo filas con datos válidos
        df_valido = df.dropna(subset=['nro suborden', 'número liq.factura'])
        
        if df_valido.empty:
            raise HTTPException(status_code=400, detail="No se encontraron registros válidos en el archivo")
        
        logger.info(f"Registros válidos encontrados: {len(df_valido)}")
        
        # Conectar a la base de datos
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Procesar cada registro
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        errores = []
        
        for index, row in df_valido.iterrows():
            try:
                nro_suborden = str(row['nro suborden']).strip()
                monto_a_pagar = float(row['monto a pagar']) if pd.notna(row['monto a pagar']) else 0
                numero_liquidacion = str(row['número liq.factura']).strip()
                fecha_liquidacion = row['fecha liq.factura']
                
                # Convertir fecha si es necesario
                if pd.notna(fecha_liquidacion):
                    if isinstance(fecha_liquidacion, str):
                        # Intentar parsear diferentes formatos de fecha
                        try:
                            fecha_liquidacion = pd.to_datetime(fecha_liquidacion).date()
                        except:
                            fecha_liquidacion = None
                    elif hasattr(fecha_liquidacion, 'date'):
                        fecha_liquidacion = fecha_liquidacion.date()
                    else:
                        fecha_liquidacion = None
                
                # Buscar la orden en ventas_retail
                buscar_query = """
                    SELECT id, numero_orden 
                    FROM ventas_retail 
                    WHERE numero_orden = %s
                """
                
                cursor.execute(buscar_query, (nro_suborden,))
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
                        monto_a_pagar,
                        orden_encontrada['id']
                    ))
                    
                    ordenes_actualizadas += 1
                    logger.info(f"Orden actualizada: {nro_suborden} -> ID {orden_encontrada['id']}")
                    
                else:
                    ordenes_no_encontradas += 1
                    logger.warning(f"Orden no encontrada: {nro_suborden}")
                    errores.append(f"Orden {nro_suborden} no encontrada en la base de datos")
                
            except Exception as e:
                logger.error(f"Error procesando fila {index}: {str(e)}")
                errores.append(f"Error en fila {index + 1}: {str(e)}")
                continue
        
        # Confirmar cambios
        connection.commit()
        
        # Preparar respuesta
        resultado = {
            "mensaje": "Liquidación procesada exitosamente",
            "archivo_procesado": archivo.filename,
            "total_procesado": len(df_valido),
            "ordenes_actualizadas": ordenes_actualizadas,
            "ordenes_no_encontradas": ordenes_no_encontradas,
            "errores": errores[:10],  # Mostrar solo los primeros 10 errores
            "fecha_procesamiento": datetime.now().isoformat()
        }
        
        logger.info(f"Procesamiento completado: {ordenes_actualizadas} actualizadas, {ordenes_no_encontradas} no encontradas")
        
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error procesando liquidación de Cencosud: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/estado/{numero_liquidacion}")
async def consultar_estado_liquidacion(numero_liquidacion: str):
    """
    Consultar el estado de una liquidación específica de Cencosud
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
                vr.precio_cliente
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
        
        return {
            "numero_liquidacion": numero_liquidacion,
            "total_ordenes": len(ordenes),
            "ordenes": ordenes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consultando liquidación {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/reportes/resumen")
async def generar_reporte_resumen():
    """
    Generar reporte resumen de liquidaciones de Cencosud
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Estadísticas generales
        stats_query = """
            SELECT 
                COUNT(*) as total_ordenes,
                SUM(CASE WHEN numero_liquidacion IS NOT NULL THEN 1 ELSE 0 END) as ordenes_con_liquidacion,
                SUM(CASE WHEN numero_liquidacion IS NULL THEN 1 ELSE 0 END) as ordenes_sin_liquidacion,
                COALESCE(SUM(monto_liquido), 0) as total_liquidado,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NULL THEN precio_cliente ELSE 0 END), 0) as total_pendiente,
                COUNT(DISTINCT numero_liquidacion) as liquidaciones_unicas
            FROM ventas_retail
            WHERE cliente_id = (SELECT id FROM clientes WHERE nombre LIKE '%cencosud%' LIMIT 1)
        """
        
        cursor.execute(stats_query)
        stats = cursor.fetchone()
        
        # Liquidaciones recientes
        recientes_query = """
            SELECT 
                numero_liquidacion,
                fecha_pago_liquidacion,
                COUNT(*) as ordenes_en_liquidacion,
                SUM(monto_liquido) as monto_total
            FROM ventas_retail
            WHERE numero_liquidacion IS NOT NULL 
            AND cliente_id = (SELECT id FROM clientes WHERE nombre LIKE '%cencosud%' LIMIT 1)
            GROUP BY numero_liquidacion, fecha_pago_liquidacion
            ORDER BY fecha_pago_liquidacion DESC
            LIMIT 10
        """
        
        cursor.execute(recientes_query)
        liquidaciones_recientes = cursor.fetchall()
        
        # Convertir fechas
        for liquidacion in liquidaciones_recientes:
            if liquidacion.get('fecha_pago_liquidacion'):
                liquidacion['fecha_pago_liquidacion'] = liquidacion['fecha_pago_liquidacion'].isoformat()
        
        return {
            "estadisticas": stats,
            "liquidaciones_recientes": liquidaciones_recientes,
            "fecha_reporte": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generando reporte de Cencosud: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()