from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # Paris devuelve un objeto. Intentamos sacar la lista de 'orders' o el objeto directo
    # Si la data es un dict con una llave 'orders' o similar, la extraemos
    if isinstance(data, dict):
        ordenes_raw = data.get('orders', data.get('content', []))
    else:
        ordenes_raw = data if isinstance(data, list) else []
    
    ordenes_finales = []

    for o in ordenes_raw:
        # 1. Extraer Número de Orden
        num_orden = o.get('originOrderNumber') or o.get('id', 'N/A')
        
        # 2. Extraer Cliente
        customer = o.get('customer', {})
        nombre_cliente = customer.get('name', 'N/A')
        
        # 3. Extraer primer producto y estado de la primera subOrder
        sub_orders = o.get('subOrders', [])
        nombre_producto = "Producto JerkHome"
        estado_desc = "PENDIENTE"
        fecha_entrega = "N/A"

        if sub_orders:
            so = sub_orders[0]
            # Estado desde el objeto status
            estado_desc = so.get('status', {}).get('description', 'PENDIENTE')
            # Fecha de entrega
            fecha_entrega = so.get('arrivalDate', 'N/A')
            # Items
            items = so.get('items', [])
            if items:
                nombre_producto = items[0].get('name', 'N/A')

        # Filtro de búsqueda manual
        if search and (search.lower() not in str(num_orden).lower() and search.lower() not in nombre_cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "cliente": nombre_cliente,
            "producto": nombre_producto,
            "entrega_comprometida": fecha_entrega,
            "estado": estado_desc.upper()
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search}
    })