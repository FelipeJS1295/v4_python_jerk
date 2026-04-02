import pandas as pd
from datetime import datetime
from db import conectar_mysql
import logging

# Configuramos el logger para que sea visible
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def procesar_excel_cencosud(ruta_archivo):
    df = pd.read_excel(ruta_archivo, header=0)
    # Normalizamos: "Número de documento" -> "numero_de_documento"
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    
    ventas = []

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

    def formatear_rut_chileno(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return ""
        rut_limpio = str(valor).replace(".", "").replace("-", "").strip().upper()
        if len(rut_limpio) < 2: return rut_limpio
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]
        return f"{cuerpo}-{dv}"

    def limpiar_a_entero(valor):
        try:
            if pd.isna(valor) or str(valor).strip() == "": return 0
            limpio = str(valor).replace("$", "").strip()
            return int(float(limpio))
        except: return 0

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

            # --- LOG DE DEPURACIÓN PARA EL RUT ---
            # Intentamos obtener el valor por nombre normalizado o por posición (columna 2)
            rut_original = row.get('numero_de_documento', row.iloc[2])
            rut_procesado = formatear_rut_chileno(rut_original)
            
            # Este mensaje aparecerá en tu terminal/consola
            logger.info(f"DEBUG RUT - Orden {numero_orden}: Original='{rut_original}' -> Procesado='{rut_procesado}'")

            # Lógica FF
            nombre_base = str(row.get('nombre_producto', "")).strip()
            es_fulfillment = str(row.get('fulfillment', "")).strip().lower()
            nombre_final = f"{nombre_base} FF" if es_fulfillment == "si" else nombre_base

            total_final = limpiar_a_entero(row.get('precio_pago_cliente', 0)) + limpiar_a_entero(row.get('costo_despacho', 0))

            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', "Sin Nombre"),
                "rut_documento": rut_procesado, # Se asigna el valor procesado
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
            logger.error(f"Error crítico en fila {index}: {e}")
            continue

    return ventas