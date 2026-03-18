from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # La API oficial devuelve una lista directamente o dentro de 'orders'
    ordenes_raw = data if isinstance(data, list) else data.get('orders', [])
    
    ordenes_finales = []
    for o in ordenes_raw:
        # Siguiendo el JSON oficial:
        num_orden = o.get('originOrderNumber') or o.get('id', 'N/A')
        cliente = o.get('customer', {}).get('name', 'N/A')
        
        sub_orders = o.get('subOrders', [])
        if not sub_orders: continue
        
        so = sub_orders[0]
        items = so.get('items', [])
        producto = items[0].get('name', 'Mueble JerkHome') if items else 'N/A'
        
        # Estado y Fecha
        estado = so.get('status', {}).get('description', 'APROBADO').upper()
        fecha_entrega = so.get('arrivalDate', 'N/A')

        if search and (search.lower() not in str(num_orden).lower() and search.lower() not in cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "cliente": cliente,
            "producto": producto,
            "entrega_comprometida": fecha_entrega,
            "estado": estado
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search or ""}
    })