import pandas as pd
from datetime import datetime
from db import conectar_mysql

def procesar_csv_ripley(ruta_archivo):
    df = pd.read_csv(
        ruta_archivo,
        sep=",",
        quotechar='"',
        skipinitialspace=True
    )

    ventas = []

    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT numero_orden FROM ventas_retail WHERE cliente_id = 4")
    ordenes_existentes = set(row[0] for row in cursor.fetchall())
    cursor.close()
    conn.close()

    for _, row in df.iterrows():
        if row.isnull().all():
            continue

        def convertir_fecha(valor):
            try:
                if pd.isna(valor):
                    return None
                if isinstance(valor, pd.Timestamp):
                    return valor.strftime("%Y-%m-%d")
                return datetime.strptime(str(valor), "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
            except:
                return None

        def limpiar_numero(valor):
            try:
                if pd.isna(valor):
                    return None
                return int(float(str(valor).replace("$", "").replace(",", "").strip()))
            except:
                return None

        numero_orden = str(row.get("order_id", "")).strip()
        if not numero_orden:
            continue

        ventas.append({
            "numero_orden": numero_orden,
            "cliente_id": 4,
            "cliente_final": f"{row.get('client_firstname', '')} {row.get('client_lastname', '')}".strip(),
            "rut_documento": row.get("client_id", None),
            "email": row.get("contact_mail", None),
            "telefono": row.get("contact_phone", None),
            "direccion": row.get("client_address", None),
            "comuna": row.get("shipping_zone_code", None),
            "region": row.get("shipping_zone_label", None),
            "sku": row.get("product_sku_0", None),
            "producto": row.get("product_title_0", None),
            "precio": limpiar_numero(row.get("price_0", None)),
            "precio_cliente": limpiar_numero(row.get("total_price", None)),
            "costo_despacho": limpiar_numero(row.get("shipping_price_0", None)),
            "courier": row.get("shipping_company", None),
            "documento": None,
            "razon_social": None,
            "rut": None,
            "giro": None,
            "direccion_factura": None,
            "fecha_compra": convertir_fecha(row.get("_created_on", None)),
            "fecha_entrega": convertir_fecha(row.get("shipping_deadline", None)),
            "fecha_cliente": None,
            "estado": "nueva",
            "unidades": 1,
            "ya_existe": numero_orden in ordenes_existentes
        })

    return ventas