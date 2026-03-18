from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # La API oficial suele devolver un objeto con una lista dentro
    if isinstance(data, dict):
        ordenes_raw = data.get('orders', data.get('content', []))
    else:
        ordenes_raw = data if isinstance(data, list) else []
    
    ordenes_finales = []
    for o in ordenes_raw:
        # Extracción según el JSON de la documentación
        num_orden = o.get('originOrderNumber') or o.get('id', 'N/A')
        cliente = o.get('customer', {}).get('name', 'N/A')
        
        sub_orders = o.get('subOrders', [])
        nombre_producto = "Mueble JerkHome"
        estado = "PENDIENTE"
        entrega = "N/A"

        if sub_orders:
            so = sub_orders[0]
            estado = so.get('status', {}).get('description', 'APROBADO').upper()
            entrega = so.get('arrivalDate', 'N/A')
            items = so.get('items', [])
            if items:
                nombre_producto = items[0].get('name', 'Mueble JerkHome')

        # Filtro de búsqueda
        if search and (search.lower() not in str(num_orden).lower() and search.lower() not in cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "cliente": cliente,
            "producto": nombre_producto,
            "entrega_comprometida": entrega,
            "estado": estado
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search or ""}
    })