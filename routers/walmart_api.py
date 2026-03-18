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

            # --- RUTA EXACTA DEL NOMBRE SEGÚN DOCUMENTACIÓN CHILE ---
            shipping_info = o.get('shippingInfo', {})
            postal = shipping_info.get('postalAddress', {})
            nombre_cliente = postal.get('name', 'N/A')

            lineas_raw = o.get('orderLines', {}).get('orderLine', [])
            if isinstance(lineas_raw, dict): lineas_raw = [lineas_raw]
            
            total_final = 0
            subtotal_items = 0
            total_envio = 0
            total_impuestos = 0
            total_descuentos = 0
            
            prod_list = []

            for l in lineas_raw:
                qty = int(l.get('orderLineQuantity', {}).get('amount', 1))
                
                # --- CÁLCULO FINANCIERO SEGÚN WALMART SELLER CENTER ---
                charges = l.get('charges', {}).get('charge', [])
                for c in charges:
                    monto = float(c.get('chargeAmount', {}).get('amount', 0))
                    impuesto_monto = float(c.get('tax', {}).get('taxAmount', {}).get('amount', 0))
                    c_name = c.get('chargeName', '')
                    
                    # Sumamos impuestos siempre
                    total_impuestos += impuesto_monto
                    
                    if c_name == 'ItemPrice':
                        subtotal_items += monto
                    elif c_name == 'Shipping':
                        total_envio += monto
                    elif c_name == 'DISCOUNT' or monto < 0:
                        total_descuentos += monto # Esto suele ser negativo, ej: -8990

                prod_list.append({
                    "nombre": l.get('item', {}).get('productName', 'Producto'),
                    "sku": l.get('item', {}).get('sku', 'N/A'),
                    "cantidad": qty,
                    "estado": l.get('orderLineStatuses', {}).get('orderLineStatus', [{}])[0].get('status', 'N/A')
                })

            # FÓRMULA FINAL: (Items + Envío + Impuestos) + Descuentos(que ya vienen negativos)
            monto_neto = subtotal_items + total_envio + total_impuestos + total_descuentos

            ordenes_finales.append({
                "id_compra": o.get('purchaseOrderId'),
                "id_orden_largo": o.get('customerOrderId'),
                "fecha": fmt_date(o.get('orderDate')),
                "limite_despacho": fmt_date(shipping_info.get('estimatedShipDate')),
                "entrega_estimada": fmt_date(shipping_info.get('estimatedDeliveryDate')),
                "cliente": {
                    "nombre": nombre_cliente,
                    "email": o.get('customerEmailId', 'N/A'),
                    "telefono": shipping_info.get('phone', 'N/A'),
                    "rut": o.get('customerRfc', 'N/A')
                },
                "destino": {
                    "calle": f"{postal.get('address1', '')} {postal.get('address2', '')}".strip(),
                    "ciudad": postal.get('city', 'N/A'),
                    "region": postal.get('state', 'N/A'),
                    "metodo": shipping_info.get('methodCode', 'N/A')
                },
                "productos": prod_list,
                "total_str": f"${monto_neto:,.0f}".replace(",", "."),
                "subtotal_str": f"${subtotal_items:,.0f}".replace(",", "."),
                "envio_str": f"${total_envio:,.0f}".replace(",", "."),
                "impuestos_str": f"${total_impuestos:,.0f}".replace(",", "."),
                "descuento_str": f"${total_descuentos:,.0f}".replace(",", "."),
                "estado_badge": prod_list[0]['estado'] if prod_list else 'N/A'
            })

        return templates.TemplateResponse("api/ventas_walmart.html", {"request": request, "ordenes": ordenes_finales})
    except Exception as e:
        return HTMLResponse(content=f"Error: {str(e)}", status_code=500)