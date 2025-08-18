import pandas as pd
from datetime import datetime
import locale
from db import conectar_mysql

try:
    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'English_United States.1252')
    except:
        pass

def procesar_excel_falabella(ruta_archivo):
    df = pd.read_excel(ruta_archivo, header=0)
    ventas = []

    conn = conectar_mysql()
    cursor = conn.cursor()

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        def convertir_fecha(valor):
            if pd.isna(valor):
                return None
            valor_str = str(valor)
            
            # Si ya es un Timestamp de pandas
            if isinstance(valor, pd.Timestamp):
                return valor.strftime("%Y-%m-%d")
            
            # Mapeo de meses en español
            meses_espanol = {
                'ene': 'Jan', 'ene.': 'Jan',
                'feb': 'Feb', 'feb.': 'Feb', 
                'mar': 'Mar', 'mar.': 'Mar',
                'abr': 'Apr', 'abr.': 'Apr',
                'may': 'May', 'may.': 'May',
                'jun': 'Jun', 'jun.': 'Jun',
                'jul': 'Jul', 'jul.': 'Jul',
                'ago': 'Aug', 'ago.': 'Aug',
                'sep': 'Sep', 'sep.': 'Sep', 'sept': 'Sep', 'sept.': 'Sep',
                'oct': 'Oct', 'oct.': 'Oct',
                'nov': 'Nov', 'nov.': 'Nov',
                'dic': 'Dec', 'dic.': 'Dec'
            }
            
            # Convertir meses en español a inglés si es necesario
            for esp, ing in meses_espanol.items():
                if esp in valor_str.lower():
                    valor_str = valor_str.lower().replace(esp, ing)
                    break
            
            try:
                # Formato: "ago. 18, 2025 16:00" -> "Aug 18, 2025 16:00"
                return datetime.strptime(valor_str, "%b %d, %Y %H:%M").strftime("%Y-%m-%d")
            except:
                try:
                    # Formato: "ago. 18, 2025" -> "Aug 18, 2025"
                    return datetime.strptime(valor_str, "%b %d, %Y").strftime("%Y-%m-%d")
                except:
                    return None

        def limpiar_numero(valor):
            try:
                return int(float(str(valor).replace(",", "").replace("CLP", "").strip()))
            except:
                return None

        numero_orden = row.iloc[4] if not pd.isna(row.iloc[4]) else None
        ya_existe = False
        if numero_orden:
            cursor.execute("SELECT COUNT(*) FROM ventas_retail WHERE numero_orden = %s", (numero_orden,))
            ya_existe = cursor.fetchone()[0] > 0

        ventas.append({
            "cliente_id": 1,
            "numero_orden": numero_orden,
            "cliente_final": row.iloc[9] if not pd.isna(row.iloc[9]) else None,
            "rut_documento": row.iloc[11] if not pd.isna(row.iloc[11]) else None,
            "email": row.iloc[62] if not pd.isna(row.iloc[62]) else None,
            "telefono": row.iloc[63] if not pd.isna(row.iloc[63]) else None,
            "fecha_compra": convertir_fecha(row.iloc[3]),
            "fecha_entrega": convertir_fecha(row.iloc[50]),
            "producto": row.iloc[40] if not pd.isna(row.iloc[40]) else None,
            "precio": limpiar_numero(row.iloc[35]),
            "precio_cliente": limpiar_numero(row.iloc[36]),
            "costo_despacho": limpiar_numero(row.iloc[37]),
            "comuna": row.iloc[18] if not pd.isna(row.iloc[18]) else None,
            "direccion": row.iloc[13] if not pd.isna(row.iloc[13]) else None,
            "region": row.iloc[22] if not pd.isna(row.iloc[22]) else None,
            "sku": row.iloc[1] if not pd.isna(row.iloc[1]) else None,
            "courier": row.iloc[42] if not pd.isna(row.iloc[42]) else None,
            "documento": row.iloc[8] if not pd.isna(row.iloc[8]) else None,
            "estado": "nueva",
            "unidades": 1,
            "ya_existe": ya_existe
        })

    cursor.close()
    conn.close()
    return ventas