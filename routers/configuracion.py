from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse # Importamos JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion_dashboard(request: Request):
    return templates.TemplateResponse("configuracion.html", {"request": request})

# --- Nueva sección: Productos Base ---
@router.get("/configuracion/productos-base", response_class=HTMLResponse)
async def configuracion_productos_base(request: Request):
    return templates.TemplateResponse("configuracion/productos_base.html", {"request": request})

@router.get("/configuracion/productos-base/total")
async def total_productos_base():
    # Aquí luego conectarás con tu DB, por ahora retornamos 0
    return JSONResponse(content={"total": 0})
# --------------------------------------

@router.get("/configuracion/clientes", response_class=HTMLResponse)
async def configuracion_clientes(request: Request):
    return templates.TemplateResponse("configuracion/clientes.html", {"request": request})

@router.get("/configuracion/insumos", response_class=HTMLResponse)
async def configuracion_insumos(request: Request):
    return templates.TemplateResponse("configuracion/insumos.html", {"request": request})

@router.get("/configuracion/proveedores", response_class=HTMLResponse)
async def configuracion_proveedores(request: Request):
    return templates.TemplateResponse("configuracion/proveedores.html", {"request": request})