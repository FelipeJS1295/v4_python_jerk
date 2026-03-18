import requests
from datetime import datetime, timedelta

# Tu API Key
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225" 

# Endpoint oficial de órdenes
url = "https://api.ecomm.cencosud.com/v1/orders"

# Cencosud pide las fechas en este formato
fecha_inicio = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

headers = {
    "ApiKey": api_key,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

params = {
    "fromDate": fecha_inicio,
    "limit": 10
}

print(f"Consultando órdenes desde {fecha_inicio}...")

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print("Respuesta del servidor:")
    print(response.text)
except Exception as e:
    print(f"Error de conexión: {str(e)}")