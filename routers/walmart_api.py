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
        return HTMLResponse(content="<h3>Error: No se pudo obtener el token de Walmart.</h3>", status_code=500)

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
            # Formateo de fechas seguro
            def fmt_date(ts):
                if not ts: return "N/A"
                return datetime.datetime.fromtimestamp(ts/1000, tz=pytz.utc).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M')

            # Procesar productos y dineros en Python (Más seguro que en HTML)
            lineas_raw = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas_raw, dict): lineas_raw = [lineas_raw]
            
            prod_list = []
            subtotal = 0
            envio = 0

            for l in lineas_raw:
                # Cantidad
                qty = int(l.get('orderLineQuantity', {}).get('amount', 1))
                
                # Buscar precios en los cargos
                item_price = 0
                charges = l.get('charges', {}).get('charge', [])
                for c in charges:
                    val = float(c.get('chargeAmount', {}).get('amount', 0))
                    c_name = c.get('chargeName', '')
                    if c_name == 'ItemPrice': 
                        item_price = val
                        subtotal += (val * qty)
                    elif c_name == 'Shipping': 
                        envio += val

                prod_list.append({
                    "nombre": l.get('item', {}).get('productName', 'Producto'),
                    "sku": l.get('item', {}).get('sku', 'N/A'),
                    "cantidad": qty,
                    "precio_unitario": f"${item_price:,.0f}".replace(",", "."),
                    "estado": l.get('orderLineQuantity', {}).get('status', 'Pendiente')
                })

            ordenes_finales.append({
                "id": o.get('purchaseOrderId'),
                "id_cliente": o.get('customerOrderId'),
                "fecha": fmt_date(o.get('orderDate')),
                "limite_despacho": fmt_date(o.get('shippingInfo', {}).get('estimatedShipDate')),
                "entrega_estimada": fmt_date(o.get('shippingInfo', {}).get('estimatedDeliveryDate')),
                "cliente": {
                    "nombre": o.get('postalAddress', {}).get('name', 'N/A'),
                    "email": o.get('customerEmailId', 'N/A'),
                    "telefono": o.get('shippingInfo', {}).get('phone', 'N/A'),
                    "rut": o.get('customerRfc', 'Sin RUT')
                },
                "destino": {
                    "calle": f"{o.get('postalAddress', {}).get('address1', '')} {o.get('postalAddress', {}).get('address2', '')}",
                    "ciudad": o.get('postalAddress', {}).get('city', 'N/A'),
                    "region": o.get('postalAddress', {}).get('state', 'N/A'),
                    "metodo": o.get('shippingInfo', {}).get('methodCode', 'N/A')
                },
                "productos": prod_list,
                "total_str": f"${(subtotal + envio):,.0f}".replace(",", "."),
                "subtotal_str": f"${subtotal:,.0f}".replace(",", "."),
                "envio_str": f"${envio:,.0f}".replace(",", "."),
                "estado_badge": prod_list[0]['estado'] if prod_list else 'N/A'
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_finales})
    except Exception as e:
        return HTMLResponse(content=f"Error Crítico: {str(e)}", status_code=500)