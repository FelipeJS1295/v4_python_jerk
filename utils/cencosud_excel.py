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

    # Helpers de limpieza
    def convertir_fecha(valor):
        if pd.isna(valor) or str(valor).strip() == "": return None
        if isinstance(valor, pd.Timestamp): return valor.strftime("%Y-%m-%d")
        formatos = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formatos:
            try: return datetime.strptime(str(valor).strip(), fmt).strftime("%Y-%m-%d")
            except: continue
        return None

    def limpiar_numero(valor):
        try:
            if pd.isna(valor): return 0
            limpio = str(valor).replace("$", "").replace(".", "").replace(",", "").strip()
            return int(float(limpio))
        except: return 0

    # 3. Procesar filas
    for index, row in df.iterrows():
        if row.isnull().all(): continue

        try:
            numero_orden = str(row.get('nro_orden', row.iloc[0])).strip()
            if not numero_orden or numero_orden == 'nan': continue

            # --- LÓGICA DE NOMBRE DE PRODUCTO (FF) ---
            nombre_base = str(row.get('nombre_producto', "")).strip()
            es_fulfillment = str(row.get('fulfillment', "")).strip().lower()
            
            # Si dice "si", agregamos el sufijo FF
            if es_fulfillment == "si":
                nombre_final = f"{nombre_base} FF"
            else:
                nombre_final = nombre_base

            # --- CÁLCULO DEL TOTAL (Precio + Despacho) ---
            pago_cliente = limpiar_numero(row.get('precio_pago_cliente', 0))
            despacho = limpiar_numero(row.get('costo_despacho', 0))
            total_venta = pago_cliente + despacho

            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', "Sin Nombre"),
                "rut_documento": row.get('número_documento', row.get('rut_cliente', "")),
                "email": row.get('email_cliente', ""),
                "telefono": row.get('telefono_cliente', ""),
                "fecha_compra": convertir_fecha(row.get('fecha_de_compra')),
                "fecha_entrega": convertir_fecha(row.get('fecha_de_entrega_prometida_al_cliente')),
                "producto": nombre_final, # Nombre con o sin FF
                "sku": row.get('sku_seller', row.get('sku_marketplace', "")),
                "precio_cliente": total_venta,
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