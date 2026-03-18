import os
import requests
from dotenv import load_dotenv

load_dotenv()

class CencosudService:
    def __init__(self):
        self.api_key = os.getenv("CENCOSUD_API_KEY")
        self.vendor_id = os.getenv("CENCOSUD_VENDOR_ID")
        # URL oficial del endpoint findAll de Marketplace
        self.url = "https://api.ecomm.cencosud.com/v1/orders"

    def obtener_ventas(self, page=1, limit=50):
        # Nombres de cabeceras ajustados según el estándar del Gateway de Cencosud
        headers = {
            "Api-Key": self.api_key,   # Nota el guion
            "Vendor-Id": self.vendor_id, # Nota el guion
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Parámetros según la documentación que enviaste
        params = {
            "page": page,
            "limit": limit
        }
        
        try:
            response = requests.get(self.url, headers=headers, params=params, timeout=15)
            
            # Veremos el Status en los logs de PM2
            print(f"CENCOSUD OFICIAL -> Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"DEBUG ERROR: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Error de red Cencosud: {str(e)}")
            return []

cenco_service = CencosudService()