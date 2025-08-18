import pandas as pd
from datetime import datetime
import locale

# Configurar locale para español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')  # Linux/Mac
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')  # Windows
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'es_CL.UTF-8')  # Chile específico
        except:
            pass

def convertir_fecha(valor):
    """
    Convierte fechas en múltiples formatos a YYYY-MM-DD
    Maneja formatos en español e inglés
    """
    if pd.isna(valor):
        return None
    
    valor_str = str(valor).strip()
    
    # Si ya es un Timestamp de pandas
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%d")
    
    # Mapeo de abreviaciones de meses en español a números
    meses_espanol = {
        'ene': '01', 'ene.': '01',
        'feb': '02', 'feb.': '02', 
        'mar': '03', 'mar.': '03',
        'abr': '04', 'abr.': '04',
        'may': '05', 'may.': '05',
        'jun': '06', 'jun.': '06',
        'jul': '07', 'jul.': '07',
        'ago': '08', 'ago.': '08',
        'sep': '09', 'sep.': '09', 'sept': '09', 'sept.': '09',
        'oct': '10', 'oct.': '10',
        'nov': '11', 'nov.': '11',
        'dic': '12', 'dic.': '12'
    }
    
    # Mapeo de meses en inglés (mantener compatibilidad)
    meses_ingles = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    try:
        # Formato 1: "ago. 18, 2025 16:00" (español con hora)
        if ',' in valor_str and ':' in valor_str:
            partes = valor_str.replace(',', '').split()
            if len(partes) >= 4:
                mes_abrev = partes[0].lower().rstrip('.')
                dia = partes[1]
                año = partes[2]
                
                # Buscar mes en español
                if mes_abrev in meses_espanol:
                    mes = meses_espanol[mes_abrev]
                    return f"{año}-{mes}-{dia.zfill(2)}"
                
                # Buscar mes en inglés (fallback)
                elif mes_abrev in meses_ingles:
                    mes = meses_ingles[mes_abrev]
                    return f"{año}-{mes}-{dia.zfill(2)}"
        
        # Formato 2: "ago. 18, 2025" (español sin hora)
        elif ',' in valor_str:
            partes = valor_str.replace(',', '').split()
            if len(partes) >= 3:
                mes_abrev = partes[0].lower().rstrip('.')
                dia = partes[1]
                año = partes[2]
                
                # Buscar mes en español
                if mes_abrev in meses_espanol:
                    mes = meses_espanol[mes_abrev]
                    return f"{año}-{mes}-{dia.zfill(2)}"
                
                # Buscar mes en inglés (fallback)
                elif mes_abrev in meses_ingles:
                    mes = meses_ingles[mes_abrev]
                    return f"{año}-{mes}-{dia.zfill(2)}"
        
        # Formato 3: Intentar con strptime para formatos estándar
        formatos_a_probar = [
            "%b %d, %Y %H:%M",  # "Jan 15, 2024 10:30" (inglés)
            "%b %d, %Y",        # "Jan 15, 2024" (inglés)
            "%d/%m/%Y",         # "18/08/2025"
            "%d-%m-%Y",         # "18-08-2025"
            "%Y-%m-%d",         # "2025-08-18"
            "%Y-%m-%d %H:%M:%S" # "2025-08-18 16:00:00"
        ]
        
        for formato in formatos_a_probar:
            try:
                fecha_obj = datetime.strptime(valor_str, formato)
                return fecha_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # Si nada funciona, retornar None
        print(f"⚠️ No se pudo convertir la fecha: '{valor_str}'")
        return None
        
    except Exception as e:
        print(f"❌ Error convirtiendo fecha '{valor_str}': {str(e)}")
        return None


# Ejemplo de uso y pruebas
if __name__ == "__main__":
    # Pruebas con diferentes formatos
    fechas_prueba = [
        "ago. 18, 2025 16:00",
        "ago. 18, 2025",
        "ene. 15, 2024 10:30",
        "dic. 31, 2023",
        "Jan 15, 2024 10:30",
        "Feb 28, 2023",
        "18/08/2025",
        "2025-08-18",
        None,
        ""
    ]
    
    print("🧪 Pruebas de conversión de fechas:")
    print("-" * 50)
    
    for fecha in fechas_prueba:
        resultado = convertir_fecha(fecha)
        print(f"'{fecha}' → '{resultado}'")