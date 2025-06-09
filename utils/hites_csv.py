import pandas as pd
from datetime import datetime
import math
from db import conectar_mysql

def limpiar_nans(data):
    for venta in data:
        for clave, valor in venta.items():
            if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
                venta[clave] = None
    return data

def procesar_archivos_hites(path_ordenes, path_detalles):
    df_ordenes = pd.read_csv(path_ordenes, sep=";", quotechar='"', skipinitialspace=True)
    df_detalles = pd.read_csv(path_detalles, sep=";", quotechar='"', skipinitialspace=True)

    df_ordenes.columns = df_ordenes.columns.str.strip().str.replace('\ufeff', '')
    df_detalles.columns = df_detalles.columns.str.strip().str.replace('\ufeff', '')

    df_detalles.rename(columns={"numeroOrden": "orderNumber"}, inplace=True)

    # Eliminar filas que contengan "Shipping"
    df_detalles = df_detalles[~df_detalles.astype(str).apply(lambda x: x.str.contains("Shipping", case=False, na=False)).any(axis=1)]

    df = pd.merge(df_ordenes, df_detalles, on="orderNumber", how="left")

    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT numero_orden FROM ventas_retail WHERE cliente_id = 5")
    ordenes_existentes = set(row[0] for row in cursor.fetchall())
    cursor.close()
    conn.close()

    ventas = []

    for _, row in df.iterrows():
        def conv_fecha(valor):
            try:
                if pd.isna(valor) or not valor:
                    return None
                valor_str = str(valor).strip()
                if len(valor_str) == 8 and valor_str.isdigit():
                    return datetime.strptime(valor_str, "%Y%m%d").strftime("%Y-%m-%d")
                return pd.to_datetime(valor_str).strftime("%Y-%m-%d")
            except:
                return None

        def limpiar(valor):
            try:
                if pd.isna(valor) or not valor:
                    return None
                return int(float(str(valor).replace(",", "").replace("$", "").strip()))
            except:
                return None

        numero_orden = str(row.get("orderNumber", "")).strip()
        if not numero_orden:
            continue

        ventas.append({
            "numero_orden": numero_orden,
            "cliente_id": 5,
            "cliente_final": f"{row.get('nombre', '')} {row.get('apellido', '')}".strip(),
            "rut_documento": row.get("rut", None),
            "email": row.get("email", None),
            "telefono": row.get("telefono", None),
            "direccion": row.get("direccion", None),
            "comuna": row.get("originName", None),
            "region": row.get("storeName", None),
            "sku": row.get("sku", None),
            "producto": row.get("producto", None),
            "precio": limpiar(row.get("precioUnitario", None)),
            "precio_cliente": limpiar(row.get("total", None)),
            "costo_despacho": limpiar(row.get("grossShippingTotal", None)),
            "courier": row.get("logisticsIntegratorName", None),
            "documento": row.get("documentNumber", None),
            "razon_social": None,
            "rut": row.get("rutSeller", None),
            "giro": None,
            "direccion_factura": None,
            "fecha_compra": conv_fecha(row.get("creation", None)),
            "fecha_entrega": conv_fecha(row.get("dateSale", None)),
            "fecha_cliente": conv_fecha(row.get("creation", None)),
            "estado": "nueva",
            "unidades": int(row.get("cantidad", 1)) if not pd.isna(row.get("cantidad")) else 1,
            "ya_existe": numero_orden in ordenes_existentes
        })

    return limpiar_nans(ventas)
