from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service
from datetime import datetime

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

# Traducción de estados basada en el campo 'status' del JSON
ESTADOS_CENCO = {
    "READY_TO_PICK": "LISTO PARA RECOLECTAR",
    "PICKING": "EN PREPARACIÓN",
    "SHIPPED": "ENVIADO",
    "DELIVERED": "ENTREGADO",
    "CANCELLED": "CANCELADO",
    "APPROVED": "APROBADO"
}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # Cencosud suele devolver una lista de objetos como el que enviaste
    ordenes_raw = data if isinstance(data, list) else data.get('content', [])
    
    ordenes_finales = []

    for o in ordenes_raw:
        # Accedemos a la primera sub-orden para los detalles logísticos
        sub_orders = o.get('subOrders', [])
        if not sub_orders: continue
        
        primera_sub = sub_orders[0]
        items = primera_sub.get('items', [])
        
        # Datos del Cliente
        customer = o.get('customer', {})
        nombre_cliente = customer.get('name', 'N/A')
        
        # Datos del Producto
        nombre_producto = items[0].get('name', 'Mueble JerkHome') if items else 'N/A'
        
        # Estado (viene dentro del objeto status de la sub-orden)
        estado_raw = primera_sub.get('status', {}).get('description', 'PENDIENTE')
        estado_latam = ESTADOS_CENCO.get(estado_raw.upper(), estado_raw).upper()

        num_orden = o.get('originOrderNumber', 'N/A') # El número que ve el cliente

        # Filtro de búsqueda
        if search and (search.lower() not in num_orden.lower() and search.lower() not in nombre_cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "fecha": o.get('createdAt', 'N/A')[:10], # Tomamos solo la fecha YYYY-MM-DD
            "limite_despacho": primera_sub.get('arrivalDate', 'N/A'),
            "cliente": nombre_cliente,
            "producto": nombre_producto,
            "estado": estado_latam
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search}
    })