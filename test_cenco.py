import requests

# Tu API Key (la que ya tienes)
api_key = "bfe830b4-2fc0-47e0-8478-2593dbf58225"

# El ID que encontraste (pruébalo aquí)
seller_id = "d5b82896-fd71-4d36-a1bc-11b4da732137" 

# USAMOS LA URL QUE VIMOS EN TU CAPTURA DE PANTALLA (marketplace.paris.cl)
url = "https://marketplace.paris.cl/api/seller/sales/orders"

headers = {
    "ApiKey": api_key,
    "x-vendor-id": seller_id, # Cencosud Paris suele usar este nombre de cabecera
    "Accept": "application/json"
}

params = {
    "page": 0,
    "size": 5
}

print(f"Probando conexión con Seller ID: {seller_id}...")

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("¡CONECTADO CON ÉXITO! Aquí están tus órdenes:")
        print(response.json())
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error de conexión: {str(e)}")