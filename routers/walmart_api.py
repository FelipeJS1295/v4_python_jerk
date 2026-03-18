from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.walmart_service import walmart_api
import datetime
import uuid
import requests
import pytz

# Definimos el router con el prefijo oficial para tu sistema
router = APIRouter(prefix="/api/marketplace", tags=["Walmart API"])

templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_walmart(request: Request):
    # ... lógica de token ...
    token = walmart_api.obtener_token()
    if not token:
        # ... error handle ...
        pass

    # Fechas (Últimos 30 días)
    hace_30_dias = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    # ... url y headers ...
    
    # ... petición ...
    response = requests.get(url, headers=headers, params={"createdStartDate": hace_30_dias, "limit": 100})
    data = response.json()
    
    ordenes_raw = data.get("list", {}).get("elements", {}).get("order", [])
    if isinstance(ordenes_raw, dict): ordenes_raw = [ordenes_raw]

    # --- NUEVA LÓGICA DE FORMATEO ---
    ordenes_formateadas = []
    tz_local = pytz.timezone('America/Santiago') # Ajusta a tu zona horaria

    for o in ordenes_raw:
        # Formatear Fecha
        fecha_dt = datetime.datetime.fromtimestamp(o.get('orderDate', 0) / 1000, tz=pytz.utc)
        fecha_local = fecha_dt.astimezone(tz_local).strftime('%d %b %Y, %H:%M')

        # Calcular Totales y Productos
        lineas = o.get('orderLines', {}).get('orderLine', [])
        if isinstance(lineas, dict): lineas = [lineas]
        
        total_monto = 0
        total_productos = 0
        productos_list = []

        for line in lineas:
            # Cantidad
            qty = line.get('orderLineQuantity', {}).get('amount', '0')
            total_productos += int(qty)
            
            # Precio (asumimos el primer cargo como el precio unitario)
            charge = line.get('charges', {}).get('charge', [{}])[0]
            price = float(charge.get('chargeAmount', {}).get('amount', 0))
            total_monto += (price * int(qty))

            productos_list.append({
                'sku': line.get('item', {}).get('sku', 'N/A'),
                'productName': line.get('item', {}).get('productName', 'Producto Sin Nombre'),
                'cantidad': qty,
                'precioUnitario': price,
                'estadoLine': line.get('orderLineQuantity', {}).get('status', 'Pendiente')
            })

        ordenes_formateadas.append({
            'purchaseOrderId': o.get('purchaseOrderId'),
            'customerOrderId': o.get('customerOrderId'),
            'fechaFormateada': fecha_local,
            'clienteNombre': o.get('postalAddress', {}).get('name', 'N/A'),
            'clienteEmail': o.get('customerEmailId', 'N/A'),
            'clienteTelefono': o.get('shippingInfo', {}).get('phone', 'N/A'),
            'direccionCompleta': f"{o.get('postalAddress', {}).get('address1', '')}, {o.get('postalAddress', {}).get('address2', '')}".strip(', '),
            'ciudad': o.get('postalAddress', {}).get('city', 'N/A'),
            'metodoEnvio': o.get('shippingInfo', {}).get('methodCode', 'N/A'),
            'estadoMokker': productos_list[0]['estadoLine'] if productos_list else 'N/A', # Estado general basado en la primera linea
            'totalMonto': total_monto,
            'totalProductos': total_productos,
            'productos': productos_list
        })

    return templates.TemplateResponse("api/ventas_walmart.html", {
        "request": request,
        "ordenes": ordenes_formateadas
    })

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