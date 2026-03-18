import requests
from datetime import datetime, timedelta

# Tu API Key
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225" 

# URL Alternativa de Producción (Ruta común en Chile)
url = "https://api.cencosud.com/v1/orders"

fecha_inicio = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')

headers = {
    "ApiKey": api_key,
    "VendorId": "", # Lo enviamos vacío para ver si el error nos dice cuál es el correcto
    "Content-Type": "application/json",
    "Accept": "application/json"
}

params = {
    "fromDate": fecha_inicio,
    "limit": 10
}

print(f"Probando conexión a: {url}")
print(f"Consultando órdenes desde: {fecha_inicio}")

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print("Respuesta:")
    print(response.text)
except Exception as e:
    print(f"Error de conexión: {str(e)}")