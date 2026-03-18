import os
import requests
from dotenv import load_dotenv

load_dotenv()

class CencosudService:
    def __init__(self):
        self.api_key = os.getenv("CENCOSUD_API_KEY")
        self.vendor_id = os.getenv("CENCOSUD_VENDOR_ID")
        # Esta es la URL de la documentación que enviaste (findAll)
        self.url = "https://api.ecomm.cencosud.com/v1/orders"

    def obtener_ventas(self, page=1, limit=50):
        # La documentación exige estas cabeceras exactas
        headers = {
            "ApiKey": self.api_key,
            "VendorId": self.vendor_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Parámetros según la documentación OrdersV1Controller_findAll
        params = {
            "page": page,
            "limit": limit
        }
        
        try:
            response = requests.get(self.url, headers=headers, params=params, timeout=15)
            
            # DEBUG: Para ver si ahora sí nos deja pasar
            print(f"DEBUG OFICIAL -> Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error API: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Error de conexión: {str(e)}")
            return []

cenco_service = CencosudService()