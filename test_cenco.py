import requests

# Tu API Key que vimos en la imagen
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225" 
url = "https://api.ecomm.cencosud.com/v1/sellers"

headers = {
    "ApiKey": api_key,
    "Accept": "application/json"
}

print("Consultando a Cencosud para buscar el Vendor ID...")
try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("¡Éxito! Estos son tus datos:")
        print(response.json())
    else:
        print(f"Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Error de conexión: {str(e)}")