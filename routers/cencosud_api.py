from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service
from datetime import datetime

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

# Traducción de estados de Paris a Español Latino
ESTADOS_CENCO = {
    "READY_TO_PICK": "LISTO PARA PICKING",
    "PICKING": "EN PREPARACIÓN",
    "SHIPPED": "ENVIADO",
    "DELIVERED": "ENTREGADO",
    "CANCELED": "CANCELADO",
    "APPROVED": "APROBADO"
}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    data = cenco_service.obtener_ventas()
    
    # Manejo de la estructura de respuesta de Paris
    if isinstance(data, dict):
        # A veces viene en 'content', otras en 'orders'
        ordenes_raw = data.get('content', data.get('orders', []))
    else:
        ordenes_raw = data if isinstance(data, list) else []
    
    ordenes_finales = []

    for o in ordenes_raw:
        # 1. Identificador de la Orden (Número que ve el cliente)
        num_orden = o.get('originOrderNumber') or o.get('id', 'N/A')
        
        # 2. Cliente
        customer = o.get('customer', {})
        nombre_cliente = customer.get('name', 'N/A')
        
        # 3. Datos de la Sub-Orden (donde vive la logística en Paris)
        sub_orders = o.get('subOrders', [])
        nombre_producto = "Producto JerkHome"
        estado_latam = "PENDIENTE"
        fecha_entrega = "N/A"

        if sub_orders:
            so = sub_orders[0] # Tomamos la primera sub-orden
            
            # Estado traducido
            estado_raw = so.get('status', {}).get('description', 'PENDIENTE')
            estado_latam = ESTADOS_CENCO.get(estado_raw.upper(), estado_raw).upper()
            
            # Fecha de entrega comprometida
            fecha_entrega = so.get('arrivalDate', 'N/A')
            
            # Nombre del producto
            items = so.get('items', [])
            if items:
                nombre_producto = items[0].get('name', 'N/A')

        # Filtro de búsqueda manual (por orden o cliente)
        if search and (search.lower() not in str(num_orden).lower() and search.lower() not in nombre_cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "cliente": nombre_cliente,
            "producto": nombre_producto,
            "entrega_comprometida": fecha_entrega,
            "estado": estado_latam,
            "fecha_creacion": o.get('createdAt', 'N/A')[:10] # YYYY-MM-DD
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search or ""}
    })