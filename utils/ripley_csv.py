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
                # Ej: 2025-10-14T02:59:59.999Z -> "2025-10-14"
                return datetime.strptime(str(valor), "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
            except:
                return None

        def ajustar_deadline_menos_1dia_fecha(valor):
            """
            Resta 1 día al ISO8601 de Ripley y devuelve solo la fecha 'YYYY-MM-DD'.
            Ej: 2025-10-14T02:59:59.999Z -> 2025-10-13
            """
            try:
                if pd.isna(valor):
                    return None
                ts = pd.to_datetime(str(valor), utc=True, errors="coerce")
                if pd.isna(ts):
                    return None
                ts2 = ts - pd.Timedelta(days=1)
                return ts2.date().isoformat()
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
            # ↙️ ahora guarda YYYY-MM-DD con 1 día menos respecto a shipping_deadline
            "fecha_entrega": ajustar_deadline_menos_1dia_fecha(row.get("shipping_deadline", None)),
            "fecha_cliente": None,
            "estado": "nueva",
            "unidades": 1,
            "ya_existe": numero_orden in ordenes_existentes
        })

    return ventas
