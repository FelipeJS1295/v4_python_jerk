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
            # Crear un savepoint para cada orden individual
            try:
                cursor.execute(f"SAVEPOINT orden_{hash(numero_orden) % 1000000}")
            except:
                pass  # Si no soporta savepoints, continuar
            
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
                    
                    # Confirmar esta orden específica si soporta savepoints
                    try:
                        cursor.execute(f"RELEASE SAVEPOINT orden_{hash(numero_orden) % 1000000}")
                    except:
                        pass
                    
                    if estado_pago == 'fallido':
                        ordenes_fallidas += 1
                    else:
                        ordenes_actualizadas += 1
                    
                    logger.info(f"Orden actualizada exitosamente: {numero_orden} -> ID {orden_encontrada['id']} (Estado: {estado_pago})")
                    
                else:
                    # Rollback solo esta orden si soporta savepoints
                    try:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT orden_{hash(numero_orden) % 1000000}")
                        cursor.execute(f"RELEASE SAVEPOINT orden_{hash(numero_orden) % 1000000}")
                    except:
                        pass
                    
                    ordenes_no_encontradas += 1
                    logger.warning(f"Orden no encontrada: {numero_orden}")
                    errores.append(f"Orden {numero_orden} no encontrada en la base de datos")
                
            except Exception as e:
                # Rollback solo esta orden específica si soporta savepoints
                try:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT orden_{hash(numero_orden) % 1000000}")
                    cursor.execute(f"RELEASE SAVEPOINT orden_{hash(numero_orden) % 1000000}")
                except:
                    pass
                
                logger.error(f"Error procesando orden {numero_orden}: {str(e)}")
                errores.append(f"Error en orden {numero_orden}: {str(e)}")
                ordenes_no_encontradas += 1
                continue
        
        # Confirmar las transacciones exitosas
        connection.commit()
        
        logger.info(f"Procesamiento Walmart completado: {ordenes_actualizadas} actualizadas, {ordenes_fallidas} fallidas, {ordenes_no_encontradas} no encontradas")
        
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
        
        logger.info(f"Resultado final: {resultado}")
        
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

@router.get("/test")
async def test_walmart():
    """Ruta de prueba para verificar que el router funciona"""
    return {"mensaje": "Router de Walmart funcionando correctamente"}