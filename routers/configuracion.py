from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion_dashboard(request: Request):
    return templates.TemplateResponse("configuracion.html", {"request": request})

@router.get("/configuracion/clientes", response_class=HTMLResponse)
async def configuracion_clientes(request: Request):
    return templates.TemplateResponse("configuracion/clientes.html", {"request": request})

@router.get("/configuracion/productos", response_class=HTMLResponse)
async def configuracion_productos(request: Request):
    return templates.TemplateResponse("configuracion/productos/index.html", {"request": request})

@router.get("/configuracion/insumos", response_class=HTMLResponse)
async def configuracion_insumos(request: Request):
    return templates.TemplateResponse("configuracion/insumos.html", {"request": request})

@router.get("/configuracion/proveedores", response_class=HTMLResponse)
async def configuracion_proveedores(request: Request):
    return templates.TemplateResponse("configuracion/proveedores.html", {"request": request})