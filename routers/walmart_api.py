from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.walmart_service import walmart_api
import datetime
import uuid
import requests
import pytz

router = APIRouter(prefix="/api/marketplace", tags=["Walmart API"])
templates = Jinja2Templates(directory="templates")

# Diccionario de traducción para Estados
ESTADOS_LATAM = {
    "Created": "Creado",
    "Acknowledged": "Lista para Enviar",
    "Shipped": "Enviado",
    "Cancelled": "Cancelado",
    "Refund": "Reembolsado",
    "Delivered": "Entregado"
}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(request: Request):
    token = walmart_api.obtener_token()
    if not token:
        return HTMLResponse(content="<h3>Error de conexión con Walmart</h3>", status_code=500)

    url = "https://marketplace.walmartapis.com/v3/orders"
    hace_30_dias = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}",
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, params={"createdStartDate": hace_30_dias, "limit": 100})
        data = response.json()
        ordenes_raw = data.get("list", {}).get("elements", {}).get("order", [])
        if isinstance(ordenes_raw, dict): ordenes_raw = [ordenes_raw]

        ordenes_finales = []
        tz_cl = pytz.timezone('America/Santiago')

        for o in ordenes_raw:
            def fmt_date(ts):
                if not ts: return "N/A"
                return datetime.datetime.fromtimestamp(ts/1000, tz=pytz.utc).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M')

            # Datos del cliente (Ubicación real según tu JSON)
            nombre_cliente = o.get('shippingInfo', {}).get('postalAddress', {}).get('name', 'N/A')

            # Datos del producto y estado
            lineas = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas, dict): lineas = [lineas]
            
            nombre_producto = lineas[0].get('item', {}).get('productName', 'N/A') if lineas else 'N/A'
            estado_raw = lineas[0].get('orderLineStatuses', {}).get('orderLineStatus', [{}])[0].get('status', 'N/A') if lineas else 'N/A'
            
            # Traducir estado a Español Latino
            estado_latam = ESTADOS_LATAM.get(estado_raw, estado_raw).upper()

            ordenes_finales.append({
                "numero_orden": o.get('customerOrderId'),
                "limite_despacho": fmt_date(o.get('shippingInfo', {}).get('estimatedShipDate')),
                "cliente": nombre_cliente,
                "producto": nombre_producto,
                "estado": estado_latam
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_finales})
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)