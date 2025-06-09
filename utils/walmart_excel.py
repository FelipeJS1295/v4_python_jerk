import pandas as pd
from datetime import datetime
from db import conectar_mysql

def procesar_excel_walmart(ruta_archivo):
    df = pd.read_excel(ruta_archivo, header=0)
    ventas = []

    conn = conectar_mysql()
    cursor = conn.cursor()

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

        numero_orden = row.iloc[1] if not pd.isna(row.iloc[1]) else None
        ya_existe = False
        if numero_orden:
            cursor.execute("SELECT COUNT(*) FROM ventas_retail WHERE numero_orden = %s", (numero_orden,))
            ya_existe = cursor.fetchone()[0] > 0

        Starken = "Starken"
        
        precio_base = limpiar_numero(row.iloc[25]) if not pd.isna(row.iloc[25]) else 0
        impuesto = limpiar_numero(row.iloc[27]) if not pd.isna(row.iloc[27]) else 0
        precio_total = precio_base + impuesto if precio_base is not None and impuesto is not None else None

        ventas.append({
            "cliente_id": 3,
            "numero_orden": numero_orden,
            "cliente_final": row.iloc[5] if not pd.isna(row.iloc[5]) else None,
            "rut_documento": row.iloc[12] if not pd.isna(row.iloc[12]) else None,
            "email": None,
            "telefono": row.iloc[7] if not pd.isna(row.iloc[7]) else None,
            "fecha_compra": convertir_fecha(row.iloc[2]),
            "fecha_entrega": convertir_fecha(row.iloc[3]),
            "fecha_cliente": convertir_fecha(row.iloc[4]),
            "producto": row.iloc[21] if not pd.isna(row.iloc[21]) else None,
            "precio": precio_base,
            "precio_cliente": precio_total,
            "costo_despacho": limpiar_numero(row.iloc[26]),
            "comuna": row.iloc[10] if not pd.isna(row.iloc[10]) else None,
            "direccion": row.iloc[8] if not pd.isna(row.iloc[8]) else None,
            "region": row.iloc[11] if not pd.isna(row.iloc[11]) else None,
            "sku": row.iloc[24] if not pd.isna(row.iloc[24]) else None,
            "courier": Starken,
            "documento": None,
            "razon_social": None,
            "rut": None,
            "giro": None,
            "direccion_factura": None,
            "estado": "nueva",
            "unidades": 1,
            "ya_existe": ya_existe
        })

    cursor.close()
    conn.close()
    return ventas
