from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # Buscamos la lista de órdenes en cualquier lugar del JSON
    ordenes_raw = []
    if isinstance(data, list):
        ordenes_raw = data
    elif isinstance(data, dict):
        # Paris suele meter la lista en 'content' o 'orders'
        ordenes_raw = data.get('content', data.get('orders', data.get('items', [])))

    ordenes_finales = []

    for o in ordenes_raw:
        # Extraemos datos con .get() para evitar errores si falta un campo
        num_orden = o.get('originOrderNumber') or o.get('orderId') or o.get('id', 'N/A')
        customer = o.get('customer', {})
        nombre_cliente = o.get('customerName') or customer.get('name') or "Cliente Paris"
        
        # Navegamos en subOrders
        sub_orders = o.get('subOrders', [])
        nombre_producto = "Producto JerkHome"
        estado_desc = "PENDIENTE"
        fecha_entrega = "N/A"

        if sub_orders:
            so = sub_orders[0]
            estado_desc = so.get('status', {}).get('description') or so.get('statusId', 'PENDIENTE')
            fecha_entrega = so.get('arrivalDate') or so.get('dispatchDate', 'N/A')
            items = so.get('items', [])
            if items:
                nombre_producto = items[0].get('name', 'Mueble JerkHome')

        # Filtro de búsqueda manual
        if search and (search.lower() not in str(num_orden).lower() and search.lower() not in nombre_cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "cliente": nombre_cliente,
            "producto": nombre_producto,
            "entrega_comprometida": fecha_entrega,
            "estado": str(estado_desc).upper()
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search or ""}
    })