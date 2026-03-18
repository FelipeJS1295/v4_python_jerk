import os
import base64
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()

class WalmartAPI:
    def __init__(self):
        # Esto se ejecuta primero y prepara las llaves
        self.client_id = os.getenv("WALMART_CLIENT_ID")
        self.client_secret = os.getenv("WALMART_CLIENT_SECRET")
        self.base_url = "https://marketplace.walmartapis.com/v3"

    def get_basic_auth(self):
        # Ahora que self.client_id existe, esto funcionará perfecto
        auth_str = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(auth_str.encode()).decode()

    def obtener_token(self):
        url = f"{self.base_url}/token"
        auth_b64 = self.get_basic_auth() # Usamos la función de arriba para no repetir código

        headers = {
            "Authorization": f"Basic {auth_b64}",
            "WM_SVC.NAME": "Walmart Marketplace",
            "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            "WM_MARKET": "cl",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            return response.json().get("access_token")
        except:
            return None

# Instancia para exportar
walmart_api = WalmartAPI()