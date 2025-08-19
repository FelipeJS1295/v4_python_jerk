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
router = APIRouter(prefix="/liquidaciones/falabella", tags=["liquidaciones-falabella"])

@router.get("/test")
async def test_falabella():
    """Ruta de prueba para verificar que el router funciona"""
    return {"mensaje": "Router de Falabella funcionando correctamente"}

@router.post("/procesar")
async def procesar_liquidacion_falabella(archivo: UploadFile = File(...)):
    """
    Procesar archivo Excel de liquidación de Falabella
    """
    connection = None
    try:
        logger.info(f"=== INICIANDO PROCESAMIENTO FALABELLA ===")
        logger.info(f"Archivo: {archivo.filename}")
        
        # Validar archivo
        if not archivo.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx o .xls)")
        
        # Leer archivo Excel
        contents = await archivo.read()
        logger.info(f"Archivo leído, tamaño: {len(contents)} bytes")
        
        try:
            # Leer Excel empezando desde la fila 5 (donde están los headers)
            df = pd.read_excel(io.BytesIO(contents), header=5)
            logger.info(f"Excel leído correctamente, filas: {len(df)}, columnas: {len(df.columns)}")
            logger.info(f"Columnas encontradas: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Error leyendo Excel: {e}")
            raise HTTPException(status_code=400, detail=f"Error leyendo Excel: {str(e)}")
        
        # Validar columnas requeridas
        columnas_requeridas = ['Nº de orden', 'Fecha de transacción', 'Nº estado de cuenta', 'Monto con IVA']
        columnas_encontradas = df.columns.tolist()
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            logger.error(f"Columnas faltantes: {columnas_faltantes}")
            raise HTTPException(
                status_code=400, 
                detail=f"Columnas faltantes: {', '.join(columnas_faltantes)}. Encontradas: {', '.join(columnas_encontradas)}"
            )
        
        # Filtrar filas válidas
        df_inicial = len(df)
        df_valido = df[df['Nº de orden'].notna() & (df['Nº de orden'] != '')]
        logger.info(f"Filas válidas (con número de orden): {len(df_valido)} de {df_inicial}")
        
        if df_valido.empty:
            raise HTTPException(status_code=400, detail="No se encontraron órdenes válidas")
        
        # Mostrar algunas filas de ejemplo
        logger.info("Primeras 3 órdenes válidas:")
        for i, row in df_valido.head(3).iterrows():
            logger.info(f"  Fila {i}: Orden={row['Nº de orden']}, Monto={row['Monto con IVA']}")
        
        # Agrupar por número de orden (similar a Walmart)
        ordenes_agrupadas = defaultdict(list)
        for index, row in df_valido.iterrows():
            try:
                numero_orden = str(row['Nº de orden']).strip()
                if numero_orden and numero_orden != 'nan':
                    ordenes_agrupadas[numero_orden].append(row)
            except Exception as e:
                logger.error(f"Error agrupando fila {index}: {e}")
                continue
        
        logger.info(f"Órdenes únicas agrupadas: {len(ordenes_agrupadas)}")
        
        # Conectar a base de datos
        try:
            connection = conectar_mysql()
            cursor = connection.cursor(dictionary=True, buffered=True)
            logger.info("Conexión a base de datos exitosa")
        except Exception as e:
            logger.error(f"Error conectando a BD: {e}")
            raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
        
        # Procesar cada orden
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        ordenes_con_error = 0
        errores = []
        
        for numero_orden, filas_orden in ordenes_agrupadas.items():
            try:
                logger.info(f"--- Procesando orden: {numero_orden} ---")
                
                if not filas_orden:
                    continue
                
                # Tomar datos comunes de la primera fila
                primera_fila = filas_orden[0]
                numero_estado_cuenta = str(primera_fila.get('Nº estado de cuenta', '')).strip()
                fecha_transaccion = primera_fila.get('Fecha de transacción')
                
                # Procesar fecha
                fecha_pago = None
                if pd.notna(fecha_transaccion):
                    try:
                        if isinstance(fecha_transaccion, str):
                            fecha_pago = pd.to_datetime(fecha_transaccion).date()
                        elif hasattr(fecha_transaccion, 'date'):
                            fecha_pago = fecha_transaccion.date()
                        else:
                            fecha_pago = pd.to_datetime(fecha_transaccion).date()
                    except:
                        logger.warning(f"No se pudo convertir fecha: {fecha_transaccion}")
                        fecha_pago = None
                
                # Sumar montos de todas las filas de la misma orden
                monto_total = 0
                for fila in filas_orden:
                    try:
                        monto_str = str(fila.get('Monto con IVA', 0))
                        monto_iva = float(monto_str) if monto_str and monto_str != 'nan' else 0
                        monto_total += monto_iva
                    except Exception as e:
                        logger.error(f"Error sumando monto en orden {numero_orden}: {e}")
                        continue
                
                logger.info(f"Orden {numero_orden}: estado_cuenta={numero_estado_cuenta}, monto_total={monto_total}, filas={len(filas_orden)}")
                
                # Buscar la orden en ventas_retail (similar a Ripley)
                orden_encontrada = None
                ordenes_buscar = [numero_orden]
                
                # Si la orden termina en -A, también buscar sin -A
                if numero_orden.endswith('-A'):
                    orden_sin_sufijo = numero_orden[:-2]
                    ordenes_buscar.append(orden_sin_sufijo)
                # Si no termina en -A, también buscar con -A
                else:
                    orden_con_sufijo = numero_orden + '-A'
                    ordenes_buscar.append(orden_con_sufijo)
                
                for orden_buscar in ordenes_buscar:
                    try:
                        cursor.execute("SELECT id, numero_orden FROM ventas_retail WHERE numero_orden = %s", (orden_buscar,))
                        orden_encontrada = cursor.fetchone()
                        
                        # Consumir resultados pendientes
                        while cursor.nextset():
                            pass
                        
                        if orden_encontrada:
                            logger.info(f"Orden encontrada con: {orden_buscar}")
                            break
                    except Exception as e:
                        logger.error(f"Error buscando orden {orden_buscar}: {e}")
                        continue
                
                if orden_encontrada:
                    try:
                        cursor.execute("""
                            UPDATE ventas_retail 
                            SET numero_liquidacion = %s, 
                                fecha_pago_liquidacion = %s, 
                                monto_liquido = %s
                            WHERE id = %s
                        """, (numero_estado_cuenta, fecha_pago, monto_total, orden_encontrada['id']))
                        
                        # Consumir resultados del UPDATE
                        while cursor.nextset():
                            pass
                        
                        ordenes_actualizadas += 1
                        logger.info(f"✅ Orden actualizada: {numero_orden} -> ID {orden_encontrada['id']}")
                        
                    except Exception as e:
                        logger.error(f"Error actualizando orden {numero_orden}: {e}")
                        ordenes_con_error += 1
                        errores.append(f"Error actualizando orden {numero_orden}: {str(e)}")
                        
                else:
                    ordenes_no_encontradas += 1
                    logger.warning(f"❌ Orden no encontrada: {numero_orden}")
                    errores.append(f"Orden {numero_orden} no encontrada en la base de datos")
                
            except Exception as e:
                logger.error(f"Error general procesando orden {numero_orden}: {e}")
                ordenes_con_error += 1
                errores.append(f"Error en orden {numero_orden}: {str(e)}")
                continue
        
        # Commit
        try:
            connection.commit()
            logger.info("✅ Transacción confirmada")
        except Exception as e:
            logger.error(f"Error en commit: {e}")
            connection.rollback()
            raise HTTPException(status_code=500, detail=f"Error confirmando cambios: {str(e)}")
        
        # Respuesta
        resultado = {
            "mensaje": "Liquidación de Falabella procesada exitosamente",
            "archivo_procesado": archivo.filename,
            "total_ordenes_procesadas": len(ordenes_agrupadas),
            "ordenes_actualizadas": ordenes_actualizadas,
            "ordenes_no_encontradas": ordenes_no_encontradas,
            "ordenes_con_error": ordenes_con_error,
            "total_filas_excel": df_inicial,
            "errores": errores[:10],  # Mostrar solo los primeros 10 errores
            "fecha_procesamiento": datetime.now().isoformat()
        }
        
        logger.info(f"=== RESULTADO FINAL FALABELLA ===")
        logger.info(f"Actualizadas: {ordenes_actualizadas}")
        logger.info(f"No encontradas: {ordenes_no_encontradas}")
        logger.info(f"Con error: {ordenes_con_error}")
        
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== ERROR CRÍTICO FALABELLA ===")
        logger.error(f"Tipo: {type(e).__name__}")
        logger.error(f"Mensaje: {str(e)}")
        
        if connection:
            try:
                connection.rollback()
            except:
                pass
                
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
    finally:
        if connection:
            try:
                connection.close()
                logger.info("Conexión cerrada")
            except:
                pass

@router.get("/estado/{numero_liquidacion}")
async def consultar_estado_liquidacion_falabella(numero_liquidacion: str):
    """
    Consultar el estado de una liquidación específica de Falabella
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
        logger.error(f"Error consultando liquidación Falabella {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()