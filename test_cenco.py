import requests
from datetime import datetime, timedelta

# Tu API Key
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225" 

# URL PRODUCTIVA OFICIAL DE CENCOSUD ECOMM
url = "https://api.ecomm.cencosud.com/marketplace/orders/v1"

fecha_inicio = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')

headers = {
    "ApiKey": api_key,
    "Content-Type": "application/json"
}

# Parámetros según su doc: findAll
params = {
    "fromDate": fecha_inicio,
    "page": 1,
    "limit": 10
}

print(f"Probando URL: {url}")

try:
    # Intentamos GET para listar
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print("Respuesta del servidor:")
    print(response.text)
except Exception as e:
    print(f"Error de red: {str(e)}")