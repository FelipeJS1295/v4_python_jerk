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

def determinar_estado_walmart(estados: List[str]) -> str:
    """
    Determinar el estado final de una orden basado en los estados de todas sus filas
    """
    try:
        estados_lower = [str(estado).lower() for estado in estados if estado]
        
        # Si hay alguna devolución, es fallido
        if any('devolucion' in estado for estado in estados_lower):
            return 'fallido'
        
        # Si todas son enviado, es pagado
        if all('enviado' in estado for estado in estados_lower):
            return 'pagado'
        
        # Cualquier otro caso es fallido
        return 'fallido'
    except Exception as e:
        logger.error(f"Error determinando estado: {e}")
        return 'fallido'

@router.get("/test")
async def test_walmart():
    """Ruta de prueba para verificar que el router funciona"""
    return {"mensaje": "Router de Walmart funcionando correctamente"}

@router.post("/procesar")
async def procesar_liquidacion_walmart(archivo: UploadFile = File(...)):
    """
    Procesar archivo CSV de liquidación de Walmart
    """
    connection = None
    try:
        logger.info(f"=== INICIANDO PROCESAMIENTO WALMART ===")
        logger.info(f"Archivo: {archivo.filename}")
        logger.info(f"Content Type: {archivo.content_type}")
        
        # Validar archivo
        if not archivo.filename.endswith('.csv'):
            logger.error(f"Archivo inválido: {archivo.filename}")
            raise HTTPException(status_code=400, detail="El archivo debe ser un CSV (.csv)")
        
        # Leer archivo CSV
        contents = await archivo.read()
        logger.info(f"Archivo leído, tamaño: {len(contents)} bytes")
        
        # Intentar con diferentes encodings
        csv_content = None
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                csv_content = contents.decode(encoding)
                logger.info(f"Archivo decodificado con encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if csv_content is None:
            raise HTTPException(status_code=400, detail="No se pudo decodificar el archivo CSV")
        
        # Verificar que pandas esté disponible
        try:
            import pandas as pd
            logger.info("Pandas importado correctamente")
        except ImportError as e:
            logger.error(f"Error importando pandas: {e}")
            raise HTTPException(status_code=500, detail="Error interno: pandas no disponible")
        
        # Leer CSV
        try:
            df = pd.read_csv(io.StringIO(csv_content), delimiter=';')
            logger.info(f"CSV leído correctamente, filas: {len(df)}, columnas: {len(df.columns)}")
            logger.info(f"Columnas encontradas: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Error leyendo CSV: {e}")
            raise HTTPException(status_code=400, detail=f"Error leyendo CSV: {str(e)}")
        
        # Validar columnas requeridas
        columnas_requeridas = ['Orden', 'Nº Liq.', 'Fecha Fin Liq.', 'Estado', 'Precio Item', 'Cargo Comision']
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
        df_valido = df.dropna(subset=['Orden', 'Nº Liq.'])
        logger.info(f"Filas válidas: {len(df_valido)} de {df_inicial}")
        
        if df_valido.empty:
            raise HTTPException(status_code=400, detail="No se encontraron registros válidos")
        
        # Mostrar algunas filas de ejemplo
        logger.info("Primeras 3 filas del CSV:")
        for i, row in df_valido.head(3).iterrows():
            logger.info(f"  Fila {i}: Orden={row.get('Orden')}, Estado={row.get('Estado')}")
        
        # Conectar a base de datos
        try:
            connection = conectar_mysql()
            cursor = connection.cursor(dictionary=True, buffered=True)  # buffered=True para evitar "unread results"
            logger.info("Conexión a base de datos exitosa")
        except Exception as e:
            logger.error(f"Error conectando a BD: {e}")
            raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
        
        # Agrupar por orden
        ordenes_agrupadas = defaultdict(list)
        for index, row in df_valido.iterrows():
            try:
                orden = str(row['Orden']).strip()
                if orden and orden != 'nan':
                    ordenes_agrupadas[orden].append(row)
            except Exception as e:
                logger.error(f"Error procesando fila {index}: {e}")
                continue
        
        logger.info(f"Órdenes únicas agrupadas: {len(ordenes_agrupadas)}")
        
        # Procesar órdenes
        ordenes_actualizadas = 0
        ordenes_no_encontradas = 0
        ordenes_fallidas = 0
        errores = []
        
        for numero_orden, filas_orden in ordenes_agrupadas.items():  # Procesar todas las órdenes
            try:
                logger.info(f"--- Procesando orden: {numero_orden} ---")
                
                if not filas_orden:
                    continue
                
                primera_fila = filas_orden[0]
                numero_liquidacion = str(primera_fila.get('Nº Liq.', '')).strip()
                fecha_fin_liquidacion = primera_fila.get('Fecha Fin Liq.')
                
                # Procesar fecha
                fecha_liquidacion = None
                if pd.notna(fecha_fin_liquidacion):
                    try:
                        fecha_liquidacion = pd.to_datetime(fecha_fin_liquidacion, format='%d-%m-%Y').date()
                    except:
                        try:
                            fecha_liquidacion = pd.to_datetime(fecha_fin_liquidacion).date()
                        except:
                            logger.warning(f"No se pudo convertir fecha: {fecha_fin_liquidacion}")
                            fecha_liquidacion = None
                
                # Calcular monto total
                monto_total = 0
                estados_orden = []
                
                for fila in filas_orden:
                    try:
                        precio_str = str(fila.get('Precio Item', 0))
                        comision_str = str(fila.get('Cargo Comision', 0))
                        
                        precio_item = float(precio_str) if precio_str and precio_str != 'nan' else 0
                        cargo_comision = float(comision_str) if comision_str and comision_str != 'nan' else 0
                        estado = str(fila.get('Estado', '')).strip()
                        
                        monto_total += precio_item + cargo_comision
                        if estado:
                            estados_orden.append(estado)
                            
                    except Exception as e:
                        logger.error(f"Error procesando fila en orden {numero_orden}: {e}")
                        continue
                
                estado_pago = determinar_estado_walmart(estados_orden)
                logger.info(f"Orden {numero_orden}: monto={monto_total}, estado={estado_pago}, filas={len(filas_orden)}")
                
                # Buscar en BD
                try:
                    cursor.execute("SELECT id, numero_orden FROM ventas_retail WHERE numero_orden = %s", (numero_orden,))
                    orden_encontrada = cursor.fetchone()
                    
                    # Asegurarse de que no hay resultados pendientes
                    while cursor.nextset():
                        pass
                    
                    if orden_encontrada:
                        cursor.execute("""
                            UPDATE ventas_retail 
                            SET numero_liquidacion = %s, fecha_pago_liquidacion = %s, monto_liquido = %s
                            WHERE id = %s
                        """, (numero_liquidacion, fecha_liquidacion, monto_total, orden_encontrada['id']))
                        
                        # Consumir resultados del UPDATE
                        while cursor.nextset():
                            pass
                        
                        ordenes_actualizadas += 1
                        logger.info(f"✅ Orden actualizada: {numero_orden}")
                        
                    else:
                        ordenes_no_encontradas += 1
                        logger.warning(f"❌ Orden no encontrada: {numero_orden}")
                        errores.append(f"Orden {numero_orden} no encontrada")
                        
                except Exception as e:
                    logger.error(f"Error BD para orden {numero_orden}: {e}")
                    ordenes_no_encontradas += 1
                    errores.append(f"Error BD en orden {numero_orden}: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error general procesando orden {numero_orden}: {e}")
                ordenes_no_encontradas += 1
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
            "mensaje": "Procesamiento completado",
            "archivo_procesado": archivo.filename,
            "total_ordenes_procesadas": len(ordenes_agrupadas),
            "ordenes_actualizadas": ordenes_actualizadas,
            "ordenes_fallidas": ordenes_fallidas,
            "ordenes_no_encontradas": ordenes_no_encontradas,
            "total_filas_csv": len(df_valido),
            "errores": errores[:10],
            "fecha_procesamiento": datetime.now().isoformat()
        }
        
        logger.info(f"=== RESULTADO FINAL ===")
        logger.info(f"Actualizadas: {ordenes_actualizadas}")
        logger.info(f"No encontradas: {ordenes_no_encontradas}")
        logger.info(f"Errores: {len(errores)}")
        
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== ERROR CRÍTICO ===")
        logger.error(f"Tipo: {type(e).__name__}")
        logger.error(f"Mensaje: {str(e)}")
        logger.error(f"Línea: {e.__traceback__.tb_lineno if e.__traceback__ else 'N/A'}")
        
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