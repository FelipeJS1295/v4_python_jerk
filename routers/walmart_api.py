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
    if not token:
        return HTMLResponse(content="<h3>Error de Token</h3>", status_code=500)

    # URL necesaria para la petición
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

        ordenes_formateadas = []
        tz_local = pytz.timezone('America/Santiago')

        for o in ordenes_raw:
            # Fecha legible
            fecha_dt = datetime.datetime.fromtimestamp(o.get('orderDate', 0) / 1000, tz=pytz.utc)
            fecha_local = fecha_dt.astimezone(tz_local).strftime('%d/%m/%Y %H:%M')

            # Procesar Líneas de Productos
            lineas = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas, dict): lineas = [lineas]
            
            prod_list = []
            total_monto = 0
            for l in lineas:
                qty = int(l.get('orderLineQuantity', {}).get('amount', 1))
                price = float(l.get('charges', {}).get('charge', [{}])[0].get('chargeAmount', {}).get('amount', 0))
                total_monto += (price * qty)
                prod_list.append({
                    "nombre": l.get('item', {}).get('productName', 'Producto'),
                    "sku": l.get('item', {}).get('sku', 'N/A'),
                    "cantidad": qty,
                    "precio": price,
                    "estado": l.get('orderLineQuantity', {}).get('status', 'Pendiente')
                })

            ordenes_formateadas.append({
                "id": o.get('purchaseOrderId'),
                "id_cliente": o.get('customerOrderId'),
                "fecha": fecha_local,
                "cliente": o.get('postalAddress', {}).get('name', 'N/A'),
                "email": o.get('customerEmailId', 'N/A'),
                "telefono": o.get('shippingInfo', {}).get('phone', 'N/A'),
                "direccion": f"{o.get('postalAddress', {}).get('address1', '')} {o.get('postalAddress', {}).get('address2', '')}",
                "ciudad": o.get('postalAddress', {}).get('city', 'N/A'),
                "region": o.get('postalAddress', {}).get('state', 'N/A'),
                "total": total_monto,
                "cant_prod": len(prod_list),
                "productos": prod_list,
                "estado_general": prod_list[0]['estado'] if prod_list else 'N/A'
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_formateadas})
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)