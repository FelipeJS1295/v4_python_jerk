from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.walmart_service import walmart_api
from datetime import datetime, timedelta
import uuid
import requests
import pytz

router = APIRouter(prefix="/api/marketplace", tags=["Walmart API"])
templates = Jinja2Templates(directory="templates")

ESTADOS_LATAM = {
    "Created": "CREADO",
    "Acknowledged": "LISTO PARA ENVIAR",
    "Shipped": "ENVIADO",
    "Cancelled": "CANCELADO"
}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(
    request: Request,
    search: str = Query(None),
    estado: str = Query(None),
    desde: str = Query(None),
    hasta: str = Query(None)
):
    token = walmart_api.obtener_token()
    url = "https://marketplace.walmartapis.com/v3/orders"
    
    # Rango de fechas por defecto (30 días) si no vienen filtros
    if not desde:
        desde_dt = (datetime.now() - timedelta(days=30))
    else:
        desde_dt = datetime.strptime(desde, "%Y-%m-%d")
        
    desde_str = desde_dt.strftime('%Y-%m-%dT00:00:00Z')
    
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}",
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, params={"createdStartDate": desde_str, "limit": 100})
        data = response.json()
        ordenes_raw = data.get("list", {}).get("elements", {}).get("order", [])
        if isinstance(ordenes_raw, dict): ordenes_raw = [ordenes_raw]

        ordenes_filtradas = []
        tz_cl = pytz.timezone('America/Santiago')

        for o in ordenes_raw:
            num_orden = o.get('customerOrderId', '')
            shipping_info = o.get('shippingInfo', {})
            nombre_cliente = shipping_info.get('postalAddress', {}).get('name', 'N/A')
            
            lineas = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas, dict): lineas = [lineas]
            
            nombre_prod = lineas[0].get('item', {}).get('productName', '') if lineas else ''
            est_raw = lineas[0].get('orderLineStatuses', {}).get('orderLineStatus', [{}])[0].get('status', 'N/A') if lineas else 'N/A'
            est_latam = ESTADOS_LATAM.get(est_raw, est_raw).upper()

            # Lógica de Filtros Manuales (Search y Estado)
            if search and (search.lower() not in num_orden.lower() and search.lower() not in nombre_cliente.lower()):
                continue
            if estado and estado != est_raw:
                continue

            ordenes_filtradas.append({
                "numero_orden": num_orden,
                "fecha_orden": datetime.fromtimestamp(o.get('orderDate', 0)/1000, tz=pytz.utc).astimezone(tz_cl).strftime('%d/%m/%Y'),
                "limite_despacho": datetime.fromtimestamp(shipping_info.get('estimatedShipDate', 0)/1000, tz=pytz.utc).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M'),
                "cliente": nombre_cliente,
                "producto": nombre_prod,
                "estado": est_latam,
                "estado_raw": est_raw
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {
            "request": request, 
            "ordenes": ordenes_filtradas,
            "filtros": {"search": search, "estado": estado, "desde": desde, "hasta": hasta}
        })
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)