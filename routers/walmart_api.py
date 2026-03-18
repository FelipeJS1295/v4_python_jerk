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
        return HTMLResponse(content="<h3>Error: Token no disponible.</h3>", status_code=500)

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
            envio_monto = 0
            prod_list = []

            for l in lineas_raw:
                qty = int(l.get('orderLineQuantity', {}).get('amount', 1))
                charges = l.get('charges', {}).get('charge', [])
                
                monto_linea_neto = 0
                for c in charges:
                    # Walmart Chile envía los montos que deben sumarse y restarse
                    monto = float(c.get('chargeAmount', {}).get('amount', 0))
                    c_name = c.get('chargeName', '')
                    
                    # Sumamos Items, Envío e Impuestos
                    if c_name in ['ItemPrice', 'Shipping', 'Tax']:
                        total_orden += monto
                        if c_name == 'ItemPrice': subtotal_items += monto
                        if c_name == 'Shipping': envio_monto += monto
                    
                    # RESTAMOS Descuentos (Discount)
                    if 'Discount' in c_name:
                        total_orden -= abs(monto)

                prod_list.append({
                    "nombre": l.get('item', {}).get('productName', 'Producto'),
                    "sku": l.get('item', {}).get('sku', 'N/A'),
                    "cantidad": qty,
                    "precio": f"${subtotal_items:,.0f}".replace(",", "."),
                    "estado": l.get('orderLineQuantity', {}).get('status', 'Pendiente')
                })

            # NOMBRE DEL CLIENTE (Corrección crítica)
            postal = o.get('postalAddress', {})
            nombre = postal.get('name')
            if not nombre or nombre == "N/A":
                nombre = f"{postal.get('firstName', '')} {postal.get('lastName', '')}".strip()
            
            ordenes_finales.append({
                "id_compra": o.get('purchaseOrderId'),
                "id_orden_largo": o.get('customerOrderId'),
                "fecha": fmt_date(o.get('orderDate')),
                "limite_despacho": fmt_date(o.get('shippingInfo', {}).get('estimatedShipDate')),
                "entrega_estimada": fmt_date(o.get('shippingInfo', {}).get('estimatedDeliveryDate')),
                "cliente": {
                    "nombre": nombre if nombre else "Cliente Marketplace",
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
                "envio_str": f"${envio_monto:,.0f}".replace(",", "."),
                "estado_badge": "Lista para enviar" if prod_list[0]['estado'] == 'Created' else prod_list[0]['estado']
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_finales})
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)