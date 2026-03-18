import os
import requests
from dotenv import load_dotenv

load_dotenv()

class CencosudService:
    def __init__(self):
        self.api_key = os.getenv("CENCOSUD_API_KEY")
        self.vendor_id = os.getenv("CENCOSUD_VENDOR_ID")
        self.url = os.getenv("CENCOSUD_URL")

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
            if response.status_code == 200:
                # Si la respuesta está vacía, retornamos lista vacía
                return response.json() if response.text else []
            return []
        except:
            return []

cenco_service = CencosudService()