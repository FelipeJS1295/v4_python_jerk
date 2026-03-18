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

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(request: Request):
    token = walmart_api.obtener_token()
    if not token: return HTMLResponse("Error Token", status_code=500)

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

        ordenes_completas = []
        tz_cl = pytz.timezone('America/Santiago')

        for o in ordenes_raw:
            # Función para convertir timestamps de Walmart (ms) a string legible
            def fmt_date(ts):
                if not ts: return "N/A"
                return datetime.datetime.fromtimestamp(ts/1000, tz=pytz.utc).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M')

            lineas = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas, dict): lineas = [lineas]
            
            # --- DESGLOSE FINANCIERO DETALLADO ---
            subtotal_items = 0
            costo_envio = 0
            
            for l in lineas:
                charges = l.get('charges', {}).get('charge', [])
                for c in charges:
                    monto = float(c.get('chargeAmount', {}).get('amount', 0))
                    if c.get('chargeName') == 'ItemPrice': subtotal_items += monto
                    if c.get('chargeName') == 'Shipping': costo_envio += monto

            ordenes_completas.append({
                "id": o.get('purchaseOrderId'),
                "id_cliente": o.get('customerOrderId'),
                "fecha_venta": fmt_date(o.get('orderDate')),
                "fecha_limite_despacho": fmt_date(o.get('shippingInfo', {}).get('estimatedShipDate')),
                "fecha_entrega_estimada": fmt_date(o.get('shippingInfo', {}).get('estimatedDeliveryDate')),
                "cliente": {
                    "nombre": o.get('postalAddress', {}).get('name'),
                    "email": o.get('customerEmailId'),
                    "telefono": o.get('shippingInfo', {}).get('phone'),
                    "rut": o.get('customerRfc', 'N/A') # Si Walmart lo envía, viene aquí
                },
                "logistica": {
                    "metodo": o.get('shippingInfo', {}).get('methodCode'),
                    "direccion": f"{o.get('postalAddress', {}).get('address1', '')} {o.get('postalAddress', {}).get('address2', '')}",
                    "ciudad": o.get('postalAddress', {}).get('city'),
                    "region": o.get('postalAddress', {}).get('state')
                },
                "productos": lineas, # Enviamos las líneas crudas para procesar en HTML
                "finanzas": {
                    "subtotal": subtotal_items,
                    "envio": costo_envio,
                    "total": subtotal_items + costo_envio
                },
                "estado": lineas[0].get('orderLineQuantity', {}).get('status') if lineas else 'N/A'
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_completas})
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)