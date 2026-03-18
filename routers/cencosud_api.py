from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from utils.cencosud_service import cenco_service
from datetime import datetime

router = APIRouter(prefix="/api/cencosud", tags=["Paris Cencosud"])
templates = Jinja2Templates(directory="templates")

# Traducción de estados según el portal de Paris que vimos
ESTADOS_PARIS = {
    "PREPARACION": "EN PREPARACIÓN",
    "ENTREGADO": "ENTREGADO",
    "EN_TRANSITO": "EN TRÁNSITO",
    "CANCELADO": "CANCELADO"
}

@router.get("/ventas", response_class=HTMLResponse)
async def ver_ventas_paris(request: Request, search: str = Query(None)):
    ordenes_raw = cenco_service.obtener_ventas()
    
    ordenes_finales = []
    # Nota: Si cencosud devuelve un objeto con lista, ajusta a: ordenes_raw.get('content', [])
    items = ordenes_raw if isinstance(ordenes_raw, list) else ordenes_raw.get('content', [])

    for o in items:
        num_orden = str(o.get('orderId', ''))
        cliente = o.get('customerName', 'N/A')
        
        # Filtro de búsqueda
        if search and (search.lower() not in num_orden.lower() and search.lower() not in cliente.lower()):
            continue

        ordenes_finales.append({
            "numero_orden": num_orden,
            "fecha": o.get('createdAt', 'N/A'), # Paris suele enviar string
            "limite_despacho": o.get('deliveryDate', 'N/A'),
            "cliente": cliente,
            "producto": o.get('items', [{}])[0].get('productName', 'Mueble JerkHome'),
            "estado": o.get('status', 'PENDIENTE').upper()
        })

    return templates.TemplateResponse("api/ventas_cencosud.html", {
        "request": request, 
        "ordenes": ordenes_finales,
        "filtros": {"search": search}
    })