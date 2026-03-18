import pandas as pd
from datetime import datetime
from db import conectar_mysql
import logging

# Configurar un logger básico para ver qué pasa
logger = logging.getLogger(__name__)

def procesar_excel_cencosud(ruta_archivo):
    # Cargamos el excel
    df = pd.read_excel(ruta_archivo, header=0)
    
    # Normalizar nombres de columnas: quitar espacios, tildes y pasar a minúsculas
    # Esto ayuda a que "Nro Orden" y "nro_orden" funcionen igual
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    
    ventas = []

    # 1. Obtener órdenes existentes para evitar duplicados (Cliente ID 2 = Cencosud/Paris)
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

    # Funciones de limpieza (se mantienen igual pero más robustas)
    def convertir_fecha(valor):
        if pd.isna(valor) or str(valor).strip() == "":
            return None
        if isinstance(valor, pd.Timestamp):
            return valor.strftime("%Y-%m-%d")
        
        formatos = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", 
            "%b %d, %Y %H:%M", "%d %b %Y", "%Y/%m/%d"
        ]
        valor_str = str(valor).strip()
        for formato in formatos:
            try:
                return datetime.strptime(valor_str, formato).strftime("%Y-%m-%d")
            except:
                continue
        return None

    def limpiar_numero(valor):
        try:
            if pd.isna(valor): return 0
            # Quitar símbolos de moneda y separadores de miles
            limpio = str(valor).replace("$", "").replace(".", "").replace(",", "").strip()
            return int(float(limpio))
        except:
            return 0

    # 2. Procesar filas
    for index, row in df.iterrows():
        # Saltamos filas vacías
        if row.isnull().all():
            continue

        # BUSQUEDA POR NOMBRE DE COLUMNA (Más seguro que el índice numérico)
        # Ajusta estos nombres según cómo aparecen exactamente en el nuevo Excel de Paris
        try:
            # Usamos .get() o acceso directo por nombre si normalizaste las columnas arriba
            numero_orden = str(row.get('nro_suborden', row.iloc[0])).strip() 
            
            if not numero_orden or numero_orden == 'nan':
                continue

            # Construimos el objeto
            # NOTA: Si prefieres seguir usando índices porque los nombres cambian mucho,
            # asegúrate de restar 1 a todos los índices que venían después de 'Nro_Devolucion'
            venta = {
                "cliente_id": 2,
                "numero_orden": numero_orden,
                "cliente_final": row.get('nombre_cliente', row.iloc[1]),
                "rut_documento": row.get('rut_cliente', row.iloc[3]),
                "email": row.get('mail_cliente', row.iloc[4]),
                "telefono": row.get('telefono_contacto', row.iloc[5]),
                "fecha_compra": convertir_fecha(row.get('fecha_compra', row.iloc[6])),
                "fecha_entrega": convertir_fecha(row.get('fecha_entrega_comprometida', row.iloc[7])),
                "producto": row.get('descripcion_producto', row.iloc[8]),
                "precio_cliente": limpiar_numero(row.get('precio_unitario', row.iloc[11])),
                "comuna": row.get('comuna_despacho', row.iloc[13]),
                "direccion": row.get('direccion_despacho', row.iloc[14]),
                "sku": row.get('sku_paris', row.iloc[17]),
                "estado": "nueva",
                "unidades": 1,
                "ya_existe": numero_orden in ordenes_existentes
            }
            
            ventas.append(venta)
            
        except Exception as e:
            logger.error(f"Error en fila {index}: {e}")
            continue

    return ventas
