from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.walmart_service import walmart_api
import datetime
import uuid
import requests

# --- ESTA ES LA LÍNEA QUE FALTA ---
router = APIRouter(prefix="/testwalmart", tags=["Walmart API"])
# ---------------------------------

@router.get("/test-orders")
async def probar_ordenes():
    # 1. Obtener el token
    token = walmart_api.obtener_token()
    if not token:
        return {"error": "No se pudo obtener el token. Revisa tus credenciales en el .env"}

    # 2. Configurar la fecha (últimos 7 días)
    hace_7_dias = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')

    # 3. Preparar la llamada a la API de Órdenes
    url = "https://marketplace.walmartapis.com/v3/orders"
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}", 
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    params = {"createdStartDate": hace_7_dias}

    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() 
    except Exception as e:
        return {"error": str(e)}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(request: Request):
    token = walmart_api.obtener_token()
    if not token:
        return "Error: No se pudo conectar con Walmart"

    # Pedimos las órdenes de los últimos 30 días para tener buen volumen
    hace_30_dias = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = "https://marketplace.walmartapis.com/v3/orders"
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}",
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers, params={"createdStartDate": hace_30_dias})
    data = response.json()
    
    # Extraemos la lista de órdenes (manejando si viene vacío)
    ordenes = data.get("list", {}).get("elements", {}).get("order", [])
    
    return templates.TemplateResponse("api/ventas_walmart.html", {
        "request": request,
        "ordenes": ordenes
    })