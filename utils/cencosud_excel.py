import pandas as pd
from datetime import datetime
from db import conectar_mysql

def procesar_excel_cencosud(ruta_archivo):
    df = pd.read_excel(ruta_archivo, header=0)
    ventas = []

    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT numero_orden FROM ventas_retail WHERE cliente_id = 2")
    ordenes_existentes = set(row[0] for row in cursor.fetchall())
    cursor.close()
    conn.close()

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        def convertir_fecha(valor):
            try:
                if pd.isna(valor):
                    return None
                if isinstance(valor, pd.Timestamp):
                    return valor.strftime("%Y-%m-%d")
                formatos = [
                    "%b %d, %Y %H:%M", "%b %d, %Y", "%d/%m/%Y", "%d-%m-%Y",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%B %d, %Y", "%d %B %Y"
                ]
                valor_str = str(valor)
                for formato in formatos:
                    try:
                        return datetime.strptime(valor_str, formato).strftime("%Y-%m-%d")
                    except:
                        continue
                return None
            except:
                return None

        def limpiar_numero(valor):
            try:
                if pd.isna(valor):
                    return None
                return int(float(str(valor).replace(",", "").replace("$", "").strip()))
            except:
                return None

        numero_orden = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else None
        if not numero_orden:
            continue

        ventas.append({
            "cliente_id": 2,
            "numero_orden": numero_orden,
            "cliente_final": row.iloc[2] if not pd.isna(row.iloc[2]) else None,
            "rut_documento": row.iloc[3] if not pd.isna(row.iloc[3]) else None,
            "email": row.iloc[4] if not pd.isna(row.iloc[4]) else None,
            "telefono": row.iloc[5] if not pd.isna(row.iloc[5]) else None,
            "fecha_compra": convertir_fecha(row.iloc[6]),
            "fecha_entrega": convertir_fecha(row.iloc[7]),
            "fecha_cliente": convertir_fecha(row.iloc[8]),
            "producto": row.iloc[9] if not pd.isna(row.iloc[9]) else None,
            "precio": limpiar_numero(row.iloc[10]),
            "precio_cliente": limpiar_numero(row.iloc[11]),
            "costo_despacho": limpiar_numero(row.iloc[12]),
            "comuna": row.iloc[13] if not pd.isna(row.iloc[13]) else None,
            "direccion": row.iloc[14] if not pd.isna(row.iloc[14]) else None,
            "region": row.iloc[15] if not pd.isna(row.iloc[15]) else None,
            "sku": row.iloc[17] if not pd.isna(row.iloc[17]) else None,
            "documento": row.iloc[19] if not pd.isna(row.iloc[19]) else None,
            "razon_social": row.iloc[20] if not pd.isna(row.iloc[20]) else None,
            "rut": row.iloc[21] if not pd.isna(row.iloc[21]) else None,
            "giro": row.iloc[22] if not pd.isna(row.iloc[22]) else None,
            "direccion_factura": row.iloc[23] if not pd.isna(row.iloc[23]) else None,
            "courier": row.iloc[27] if not pd.isna(row.iloc[27]) else None,
            "estado": "nueva",
            "unidades": 1,
            "ya_existe": numero_orden in ordenes_existentes
        })

    return ventas
