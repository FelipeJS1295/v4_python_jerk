import pandas as pd
from datetime import datetime
from db import conectar_mysql
import logging

logger = logging.getLogger(__name__)

def procesar_excel_cencosud(ruta_archivo):
    # 1. Cargar y normalizar nombres de columnas
    df = pd.read_excel(ruta_archivo, header=0)
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    
    ventas = []

    # 2. Obtener órdenes existentes
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

    # --- FUNCIÓN DE LIMPIEZA PARA NÚMEROS ENTEROS ---
    def limpiar_a_entero(valor):
        try:
            if pd.isna(valor) or str(valor).strip() == "": 
                return 0
            # Eliminamos símbolos de moneda y separadores de miles comunes
            limpio = str(valor).replace("$", "").replace(".", "").replace(",", "").strip()
            # Convertimos a float primero por si trae ".00" y luego a int para eliminar el decimal
            return int(float(limpio))
        except (ValueError, TypeError):
            return 0

    def convertir_fecha(valor):
        if pd.isna(valor) or str(valor).strip() == "": return None
        if isinstance(valor, pd.Timestamp): return valor.strftime("%Y-%m-%d")
        formatos = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formatos:
            try: return datetime.strptime(str(valor).strip(), fmt).strftime("%Y-%m-%d")
            except: continue
        return None

    # 3. Procesar filas
    for index, row in df.iterrows():
        if row.isnull().all(): continue

        try:
            numero_orden = str(row.get('nro_orden', row.iloc[0])).strip()
            if not numero_orden or numero_orden == 'nan': continue

            # Lógica FF para el nombre del producto
            nombre_base = str(row.get('nombre_producto', "")).strip()
            es_fulfillment = str(row.get('fulfillment', "")).strip().lower()
            nombre_final = f"{nombre_base} FF" if es_fulfillment == "si" else nombre_base

            # --- LIMPIEZA DE NÚMEROS SOLICITADA ---
            # Aplicamos la limpieza a las 3 columnas específicas
            precio_unitario = limpiar_a_entero(row.get('precio', 0))
            pago_cliente    = limpiar_a_entero(row.get('precio_pago_cliente', 0))
            costo_despacho  = limpiar_a_entero(row.get('costo_despacho', 0))
            
            # El total que va a la base de datos es la suma de pago + despacho
            total_final = pago_cliente + costo_despacho

            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', "Sin Nombre"),
                "rut_documento": row.get('número_documento', ""),
                "email": row.get('email_cliente', ""),
                "telefono": row.get('telefono_cliente', ""),
                "fecha_compra": convertir_fecha(row.get('fecha_de_compra')),
                "fecha_entrega": convertir_fecha(row.get('fecha_de_entrega_prometida_al_cliente')),
                "producto": nombre_final,
                "sku": row.get('sku_seller', row.get('sku_marketplace', "")),
                "precio_cliente": total_final, # Suma como entero
                "comuna": row.get('comuna', ""),
                "direccion": row.get('dirección_de_envío', ""),
                "estado": "nueva",
                "unidades": 1,
                "ya_existe": numero_orden in ordenes_existentes
            }
            
            ventas.append(venta)
            
        except Exception as e:
            logger.error(f"Error en fila {index}: {e}")
            continue

    return ventas