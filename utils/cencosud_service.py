import os
import requests
from dotenv import load_dotenv

load_dotenv()

class CencosudService:
    def __init__(self):
        self.api_key = os.getenv("CENCOSUD_API_KEY")
        self.vendor_id = os.getenv("CENCOSUD_VENDOR_ID")
        # Usamos la URL que confirmamos en el navegador
        self.url = "https://marketplace.paris.cl/api/seller/sales/orders"

    def obtener_ventas(self, page=0, size=50):
        headers = {
            "ApiKey": self.api_key,
            "x-vendor-id": self.vendor_id,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        params = {"page": page, "size": size}
        
        try:
            response = requests.get(self.url, headers=headers, params=params)
            # LOG PARA DEBUG: Esto lo verás en 'pm2 logs jerkhome-admin'
            print(f"DEBUG PARIS -> Status: {response.status_code} | Body: {response.text[:200]}")
            
            if response.status_code == 200 and response.text:
                return response.json()
            return []
        except Exception as e:
            print(f"ERROR CRÍTICO PARIS: {str(e)}")
            return []

cenco_service = CencosudService()