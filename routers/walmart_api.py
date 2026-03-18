from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.walmart_service import walmart_api
import datetime
import uuid
import requests

# Definimos el router con el prefijo oficial para tu sistema
router = APIRouter(prefix="/api/marketplace", tags=["Walmart API"])

templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(request: Request):
    """
    Obtiene las ventas de los últimos 30 días directamente de la API de Walmart
    y las muestra en una tabla sin guardar en base de datos local.
    """
    # 1. Obtener Token de acceso
    token = walmart_api.obtener_token()
    if not token:
        return HTMLResponse(content="<h3>Error: No se pudo obtener el token de Walmart. Revisa el archivo .env</h3>", status_code=500)

    # 2. Configurar la fecha de consulta (últimos 30 días)
    hace_30_dias = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # 3. Preparar la petición a Walmart
    url = "https://marketplace.walmartapis.com/v3/orders"
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}",
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    params = {
        "createdStartDate": hace_30_dias,
        "limit": 100  # Ajustamos el límite para ver más órdenes de una vez
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 4. Navegar por el JSON de Walmart para llegar a la lista de órdenes
        # Estructura: data -> list -> elements -> order (lista)
        ordenes = data.get("list", {}).get("elements", {}).get("order", [])
        
        # 5. Retornar la vista con los datos
        return templates.TemplateResponse("api/ventas_walmart.html", {
            "request": request,
            "ordenes": ordenes
        })

    except Exception as e:
        return HTMLResponse(content=f"<h3>Error al conectar con la API de Walmart: {str(e)}</h3>", status_code=500)

@router.get("/test-orders")
async def probar_ordenes_raw():
    """
    Ruta de respaldo para ver el JSON crudo en caso de dudas
    """
    token = walmart_api.obtener_token()
    if not token:
        return {"error": "Token fallido"}

    hace_7_dias = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = "https://marketplace.walmartapis.com/v3/orders"
    
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}",
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers, params={"createdStartDate": hace_7_dias})
    return response.json()