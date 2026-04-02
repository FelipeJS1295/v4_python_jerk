import pandas as pd
from datetime import datetime
from db import conectar_mysql
import logging

logger = logging.getLogger(__name__)

def procesar_excel_cencosud(ruta_archivo):
    df = pd.read_excel(ruta_archivo, header=0)
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    
    ventas = []

    # 1. Obtener órdenes existentes
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

    # --- NUEVA FUNCIÓN PARA FORMATEAR RUT ---
    def formatear_rut_chileno(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return ""
        # Limpiamos espacios, puntos y guiones previos para normalizar
        rut_limpio = str(valor).replace(".", "").replace("-", "").strip().upper()
        
        if len(rut_limpio) < 2:
            return rut_limpio
        
        # Separamos el cuerpo del dígito verificador y ponemos el guion
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]
        return f"{cuerpo}-{dv}"

    # --- LIMPIEZA DE NÚMEROS CORREGIDA (EVITA EL CERO EXTRA) ---
    def limpiar_a_entero(valor):
        try:
            if pd.isna(valor) or str(valor).strip() == "": 
                return 0
            # Solo quitamos el signo $, NO los puntos decimales todavía
            limpio = str(valor).replace("$", "").strip()
            # Convertir a float (entiende el .00) y luego a int (lo elimina)
            return int(float(limpio))
        except:
            return 0

    def convertir_fecha(valor):
        if pd.isna(valor) or str(valor).strip() == "": return None
        if isinstance(valor, pd.Timestamp): return valor.strftime("%Y-%m-%d")
        formatos = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formatos:
            try: return datetime.strptime(str(valor).strip(), fmt).strftime("%Y-%m-%d")
            except: continue
        return None

    # 2. Procesar filas
    for index, row in df.iterrows():
        if row.isnull().all(): continue

        try:
            numero_orden = str(row.get('nro_orden', row.iloc[0])).strip()
            if not numero_orden or numero_orden == 'nan': continue

            # Lógica FF
            nombre_base = str(row.get('nombre_producto', "")).strip()
            es_fulfillment = str(row.get('fulfillment', "")).strip().lower()
            nombre_final = f"{nombre_base} FF" if es_fulfillment == "si" else nombre_base

            # Cálculos de dinero (Ya no agregan ceros extra)
            pago_cliente = limpiar_a_entero(row.get('precio_pago_cliente', 0))
            costo_despacho = limpiar_a_entero(row.get('costo_despacho', 0))
            total_final = pago_cliente + costo_despacho

            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', "Sin Nombre"),
                # --- APLICAMOS EL FORMATO DE RUT AQUÍ ---
                "rut_documento": formatear_rut_chileno(row.get('número_documento', "")),
                "email": row.get('email_cliente', ""),
                "telefono": row.get('telefono_cliente', ""),
                "fecha_compra": convertir_fecha(row.get('fecha_de_compra')),
                "fecha_entrega": convertir_fecha(row.get('fecha_de_entrega_prometida_al_cliente')),
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
            logger.error(f"Error en fila {index}: {e}")
            continue

    return ventas