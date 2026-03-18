import requests
from datetime import datetime, timedelta

# Tu API Key
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225" 

# Probaremos con las 2 variantes más probables en Chile
urls_a_probar = [
    "https://api.ecomm.cencosud.com/cl/v1/orders",
    "https://api.ecomm.cencosud.com/v1/marketplace/orders"
]

fecha_inicio = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')

headers = {
    "ApiKey": api_key,
    "Content-Type": "application/json"
}

params = {
    "fromDate": fecha_inicio,
    "limit": 10
}

for url in urls_a_probar:
    print(f"\n--- Probando: {url} ---")
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Respuesta: {response.text}")
    except Exception as e:
        print(f"Error de conexión: {str(e)}")