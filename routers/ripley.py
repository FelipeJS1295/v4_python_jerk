from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from db import conectar_mysql
from typing import Optional
import pandas as pd
import logging
from datetime import datetime
import io

# Configurar logging
logger = logging.getLogger(__name__)

# Crear el router
router = APIRouter(prefix="/liquidaciones/ripley", tags=["liquidaciones-ripley"])

@router.get("/test")
async def test_ripley():
    """Ruta de prueba para verificar que el router funciona"""
    return {"mensaje": "Router de Ripley funcionando correctamente"}

@router.post("/procesar")
async def procesar_liquidacion_ripley(
    archivo: UploadFile = File(...),
    fecha_liquidacion: str = Form(..., description="Fecha de liquidación en formato YYYY-MM-DD")
):
    """
    Procesar archivo Excel de liquidación de Ripley
    """
    connection = None
    try:
        logger.info(f"=== INICIANDO PROCESAMIENTO RIPLEY ===")
        logger.info(f"Archivo: {archivo.filename}")
        logger.info(f"Fecha liquidación proporcionada: {fecha_liquidacion}")
        
        # Validar archivo
        if not archivo.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx o .xls)")
        
        # Validar fecha
        try:
            fecha_pago = datetime.strptime(fecha_liquidacion, '%Y-%m-%d').date()
            logger.info(f"Fecha de pago convertida: {fecha_pago}")
        except ValueError:
            raise HTTPException(status_code=400, detail="Fecha inválida. Use formato YYYY-MM-DD")
        
        # Leer archivo Excel
        contents = await archivo.read()
        logger.info(f"Archivo leído, tamaño: {len(contents)} bytes")
        
        try:
            df = pd.read_excel(io.BytesIO(contents))
            logger.info(f"Excel leído correctamente, filas: {len(df)}, columnas: {len(df.columns)}")
            logger.info(f"Columnas encontradas: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Error leyendo Excel: {e}")
            raise HTTPException(status_code=400, detail=f"Error leyendo Excel: {str(e)}")
        
        # Validar columnas requeridas
        columnas_requeridas = ['Número documento liquidación', 'Orden de compra', 'A pagar']
        columnas_encontradas = df.columns.tolist()
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            logger.error(f"Columnas faltantes: {columnas_faltantes}")
            raise HTTPException(
                status_code=400, 
                detail=f"Columnas faltantes: {', '.join(columnas_faltantes)}. Encontradas: {', '.join(columnas_encontradas)}"
            )
        
        # Filtrar filas con orden de compra válida
        df_inicial = len(df)
        df_valido = df[df['Orden de compra'].notna() & (df['Orden de compra'] != '')]
        logger.info(f"Filas válidas (con orden de compra): {len(df_valido)} de {df_inicial}")
        
        if df_valido.empty:
            raise HTTPException(status_code=400, detail="No se encontraron órdenes de compra válidas")
        
        # Obtener número de liquidación (usar el primero que no sea nulo)
        numero_liquidacion_base = None
        for valor in df['Número documento liquidación'].dropna():
            if pd.notna(valor) and str(valor).strip():
                numero_liquidacion_base = str(valor).strip()
                break
        
        if not numero_liquidacion_base:
            raise HTTPException(status_code=400, detail="No se encontró número de liquidación en el archivo")
        
        logger.info(f"Número de liquidación detectado: {numero_liquidacion_base}")
        
        # Mostrar algunas filas de ejemplo
        logger.info("Primeras 3 órdenes válidas:")
        for i, row in df_valido.head(3).iterrows():
            logger.info(f"  Fila {i}: Orden={row['Orden de compra']}, A pagar={row['A pagar']}")
        
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
        
        for index, row in df_valido.iterrows():
            try:
                orden_compra = str(row['Orden de compra']).strip()
                a_pagar = row['A pagar']
                
                # Usar número de liquidación del archivo o el detectado
                numero_liquidacion = str(row.get('Número documento liquidación', numero_liquidacion_base)).strip()
                if not numero_liquidacion or numero_liquidacion == 'nan':
                    numero_liquidacion = numero_liquidacion_base
                
                # Procesar monto
                try:
                    monto_liquido = float(a_pagar) if pd.notna(a_pagar) else 0
                except (ValueError, TypeError):
                    monto_liquido = 0
                    logger.warning(f"No se pudo convertir 'A pagar' para orden {orden_compra}: {a_pagar}")
                
                logger.info(f"--- Procesando orden: {orden_compra} ---")
                logger.info(f"Número liquidación: {numero_liquidacion}")
                logger.info(f"Monto líquido: {monto_liquido}")
                
                # Buscar en BD (probar con y sin el sufijo -A)
                orden_encontrada = None
                ordenes_buscar = [orden_compra]
                
                # Si la orden termina en -A, también buscar sin -A
                if orden_compra.endswith('-A'):
                    orden_sin_sufijo = orden_compra[:-2]
                    ordenes_buscar.append(orden_sin_sufijo)
                # Si no termina en -A, también buscar con -A
                else:
                    orden_con_sufijo = orden_compra + '-A'
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
                        """, (numero_liquidacion, fecha_pago, monto_liquido, orden_encontrada['id']))
                        
                        # Consumir resultados del UPDATE
                        while cursor.nextset():
                            pass
                        
                        ordenes_actualizadas += 1
                        logger.info(f"✅ Orden actualizada: {orden_compra} -> ID {orden_encontrada['id']}")
                        
                    except Exception as e:
                        logger.error(f"Error actualizando orden {orden_compra}: {e}")
                        ordenes_con_error += 1
                        errores.append(f"Error actualizando orden {orden_compra}: {str(e)}")
                        
                else:
                    ordenes_no_encontradas += 1
                    logger.warning(f"❌ Orden no encontrada: {orden_compra}")
                    errores.append(f"Orden {orden_compra} no encontrada en la base de datos")
                
            except Exception as e:
                logger.error(f"Error general procesando fila {index}: {e}")
                ordenes_con_error += 1
                errores.append(f"Error en fila {index + 1}: {str(e)}")
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
            "mensaje": "Liquidación de Ripley procesada exitosamente",
            "archivo_procesado": archivo.filename,
            "numero_liquidacion": numero_liquidacion_base,
            "fecha_liquidacion": fecha_liquidacion,
            "total_ordenes_procesadas": len(df_valido),
            "ordenes_actualizadas": ordenes_actualizadas,
            "ordenes_no_encontradas": ordenes_no_encontradas,
            "ordenes_con_error": ordenes_con_error,
            "total_filas_excel": df_inicial,
            "errores": errores[:10],  # Mostrar solo los primeros 10 errores
            "fecha_procesamiento": datetime.now().isoformat()
        }
        
        logger.info(f"=== RESULTADO FINAL RIPLEY ===")
        logger.info(f"Actualizadas: {ordenes_actualizadas}")
        logger.info(f"No encontradas: {ordenes_no_encontradas}")
        logger.info(f"Con error: {ordenes_con_error}")
        logger.info(f"Número liquidación: {numero_liquidacion_base}")
        
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== ERROR CRÍTICO RIPLEY ===")
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
async def consultar_estado_liquidacion_ripley(numero_liquidacion: str):
    """
    Consultar el estado de una liquidación específica de Ripley
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
        logger.error(f"Error consultando liquidación Ripley {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()