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
        return HTMLResponse(content="<h3>Error: Token de Walmart no disponible.</h3>", status_code=500)

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

            lineas_raw = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas_raw, dict): lineas_raw = [lineas_raw]
            
            total_orden = 0
            subtotal_items = 0
            envio_items = 0
            prod_list = []

            for l in lineas_raw:
                qty = int(l.get('orderLineQuantity', {}).get('amount', 1))
                
                # Sumar todos los cargos de la línea para el total real
                charges = l.get('charges', {}).get('charge', [])
                for c in charges:
                    monto_cargo = float(c.get('chargeAmount', {}).get('amount', 0))
                    total_orden += monto_cargo
                    if c.get('chargeName') == 'ItemPrice': subtotal_items += monto_cargo
                    if c.get('chargeName') == 'Shipping': envio_items += monto_cargo

                prod_list.append({
                    "nombre": l.get('item', {}).get('productName', 'Producto'),
                    "sku": l.get('item', {}).get('sku', 'N/A'),
                    "cantidad": qty,
                    "precio": f"${float(l.get('charges', {}).get('charge', [{}])[0].get('chargeAmount', {}).get('amount', 0)):,.0f}".replace(",", "."),
                    "estado": l.get('orderLineQuantity', {}).get('status', 'Pendiente')
                })

            # Extracción robusta del nombre del cliente
            postal = o.get('postalAddress', {})
            nombre_cliente = postal.get('name')
            if not nombre_cliente or nombre_cliente == "N/A":
                nombre_cliente = f"{postal.get('firstName', '')} {postal.get('lastName', '')}".strip()
            
            if not nombre_cliente: nombre_cliente = "Cliente Walmart"

            ordenes_finales.append({
                "id_compra": o.get('purchaseOrderId'), # Ej: P111...
                "id_orden_largo": o.get('customerOrderId'), # El número de orden largo
                "fecha": fmt_date(o.get('orderDate')),
                "limite_despacho": fmt_date(o.get('shippingInfo', {}).get('estimatedShipDate')),
                "entrega_estimada": fmt_date(o.get('shippingInfo', {}).get('estimatedDeliveryDate')),
                "cliente": {
                    "nombre": nombre_cliente,
                    "email": o.get('customerEmailId', 'N/A'),
                    "telefono": o.get('shippingInfo', {}).get('phone', 'N/A'),
                    "rut": o.get('customerRfc', 'Sin RUT')
                },
                "destino": {
                    "calle": f"{postal.get('address1', '')} {postal.get('address2', '')}".strip(),
                    "ciudad": postal.get('city', 'N/A'),
                    "region": postal.get('state', 'N/A'),
                    "metodo": o.get('shippingInfo', {}).get('methodCode', 'N/A')
                },
                "productos": prod_list,
                "total_str": f"${total_orden:,.0f}".replace(",", "."),
                "subtotal_str": f"${subtotal_items:,.0f}".replace(",", "."),
                "envio_str": f"${envio_items:,.0f}".replace(",", "."),
                "estado_badge": prod_list[0]['estado'] if prod_list else 'N/A'
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_finales})
    except Exception as e:
        return HTMLResponse(content=f"Error en servidor: {str(e)}", status_code=500)