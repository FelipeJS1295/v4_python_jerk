import pandas as pd
from datetime import datetime
from db import conectar_mysql
import logging

# Configuración de logging para ver procesos en consola
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def procesar_excel_cencosud(ruta_archivo):
    # 1. Cargar Excel y normalizar nombres de columnas
    # Esto convierte "Número de documento" en "numero_de_documento", etc.
    df = pd.read_excel(ruta_archivo, header=0)
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    
    ventas = []

    # 2. Obtener órdenes existentes para evitar duplicados
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT numero_orden FROM ventas_retail WHERE cliente_id = 2")
        ordenes_existentes = set(str(row[0]).strip() for row in cursor.fetchall())
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error consultando BD: {e}")
        ordenes_existentes = set()

    # --- FUNCIONES DE LIMPIEZA ---

    def formatear_rut_chileno(valor):
        """Convierte 8020244K en 8020244-K"""
        if pd.isna(valor) or str(valor).strip() == "":
            return ""
        rut_limpio = str(valor).replace(".", "").replace("-", "").strip().upper()
        if len(rut_limpio) < 2: return rut_limpio
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]
        return f"{cuerpo}-{dv}"

    def limpiar_a_entero(valor):
        """Convierte montos con .00 en enteros limpios"""
        try:
            if pd.isna(valor) or str(valor).strip() == "": return 0
            # Solo quitamos el $, dejamos que float() maneje el punto decimal del Excel
            limpio = str(valor).replace("$", "").strip()
            return int(float(limpio))
        except: return 0

    def convertir_fecha(valor):
        """Estandariza fechas a formato YYYY-MM-DD"""
        if pd.isna(valor) or str(valor).strip() == "": return None
        if isinstance(valor, pd.Timestamp): return valor.strftime("%Y-%m-%d")
        
        formatos = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        valor_str = str(valor).strip()
        for fmt in formatos:
            try:
                return datetime.strptime(valor_str, fmt).strftime("%Y-%m-%d")
            except:
                continue
        return None

    # 3. Procesar filas
    for index, row in df.iterrows():
        if row.isnull().all(): continue

        try:
            # Identificador de la orden
            numero_orden = str(row.get('nro_orden', row.iloc[0])).strip()
            if not numero_orden or numero_orden == 'nan': continue

            # RUT: Buscamos por nombre normalizado o posición
            rut_original = row.get('numero_de_documento', row.iloc[2])
            rut_procesado = formatear_rut_chileno(rut_original)
            
            # Log de depuración para seguimiento
            logger.info(f"DEBUG RUT - Orden {numero_orden}: Original='{rut_original}' -> Procesado='{rut_procesado}'")

            # Lógica de Producto con sufijo FF
            nombre_base = str(row.get('nombre_producto', "")).strip()
            es_fulfillment = str(row.get('fulfillment', "")).strip().lower()
            nombre_final = f"{nombre_base} FF" if es_fulfillment == "si" else nombre_base

            # Cálculo de Monto Total (Precio Pago + Despacho)
            pago_cliente = limpiar_a_entero(row.get('precio_pago_cliente', 0))
            costo_despacho = limpiar_a_entero(row.get('costo_despacho', 0))
            total_final = pago_cliente + costo_despacho

            # Captura de las 3 fechas específicas
            f_compra = convertir_fecha(row.get('fecha_de_compra'))
            f_entrega = convertir_fecha(row.get('fecha_de_entrega_al_courier'))
            f_cliente = convertir_fecha(row.get('fecha_de_entrega_prometida_al_cliente'))

            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', "Sin Nombre"),
                "rut_documento": rut_procesado,
                "email": row.get('email_cliente', ""),
                "telefono": row.get('telefono_cliente', ""),
                "fecha_compra": f_compra,
                "fecha_entrega": f_entrega,
                "fecha_cliente": f_cliente, 
                "producto": nombre_final,
                "sku": row.get('sku_seller', row.get('sku_marketplace', "")),
                "precio_cliente": total_final,
                "comuna": row.get('comuna', ""),
                "direccion": row.get('dirección_de_envío', ""),
                "estado": "nueva",
                "unidades": 1,
                "ya_existe": numero_orden in ordenes_existentes
            }
            
            ventas.append(venta)
            
        except Exception as e:
            logger.error(f"Error crítico en fila {index}: {e}")
            continue

    return ventas