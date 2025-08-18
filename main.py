from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os

# Routers generales
from routers import (
    clientes,
    insumos,
    proveedores,
    productos,
    producto_insumo,
    ventas,
    importar_falabella,
    importar_cencosud,
    importar_walmart,
    importar_ripley,
    importar_hites,
    manual,
    produccion,
    trabajadores,
    ventas_maestra,
    dashboard,
    usuarios,
    configuracion,
    finanzas,
    ecomerce,
    image_router,
    usuarios_jinja,
    trabajadores_jinja,
)

from routers import camaras
from routers.config import trabajadores_acciones
from routers.config import usuarios_acciones
from routers.logistica import devoluciones
from routers.logistica.bodega import facturas

# Routers de configuración
from routers.config import (
    clientes as config_clientes,
    insumos as config_insumos,
    proveedores as config_proveedores,
)

from routers.auth import router as auth_router, obtener_usuario_actual

# App y configuración
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos y templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/imagenes", StaticFiles(directory="/var/www/imagenes_jhk"), name="imagenes")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ===== RUTAS PÚBLICAS (no requieren autenticación) =====
RUTAS_PUBLICAS = {
    "/auth/login",
    "/auth/logout", 
    "/usuarios/login",
}

def es_ruta_publica(path: str) -> bool:
    """Verificar si una ruta es pública"""
    return (
        any(path.startswith(ruta) for ruta in RUTAS_PUBLICAS) or
        path.startswith("/static") or
        path.startswith("/imagenes")
    )

def es_ruta_api(path: str) -> bool:
    """Verificar si una ruta es de API y necesita usuario en el state"""
    return "/api/" in path

# ===== MIDDLEWARE DE AUTENTICACIÓN =====
@app.middleware("http")
async def verificar_autenticacion(request: Request, call_next):
    """Middleware para verificar autenticación en todas las rutas protegidas"""
    
    ruta_actual = request.url.path
    
    # Verificar si es una ruta pública
    if es_ruta_publica(ruta_actual):
        response = await call_next(request)
        return response
    
    # Para rutas protegidas, verificar autenticación
    usuario = obtener_usuario_actual(request)
    
    # Si es una ruta de API y no hay usuario, retornar error JSON
    if es_ruta_api(ruta_actual) and not usuario:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "No autenticado", "redirect": "/auth/login"}
        )
    
    if not usuario:
        # No autenticado, redirigir según la ruta
        if ruta_actual == "/":
            # Para la ruta raíz, mostrar el login directamente
            return templates.TemplateResponse("auth/login.html", {"request": request})
        else:
            # Para otras rutas, redirigir a login
            return RedirectResponse(url="/auth/login", status_code=302)
    
    # Usuario válido, agregar al request state
    request.state.usuario = usuario
    
    # Continuar con la solicitud
    response = await call_next(request)
    return response

# ===== RUTA RAÍZ =====
@app.get("/")
def home(request: Request):
    """Dashboard principal - Protegido por middleware"""
    # El middleware ya verificó la autenticación
    usuario = getattr(request.state, 'usuario', None)
    
    if usuario:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "usuario": usuario
        })
    else:
        # Fallback (no debería pasar por el middleware)
        return templates.TemplateResponse("auth/login.html", {"request": request})

# ===== RUTA DE DASHBOARD ADICIONAL =====
@app.get("/dashboard")
def dashboard_principal(request: Request):
    """Dashboard alternativo - También protegido"""
    usuario = getattr(request.state, 'usuario', None)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": usuario
    })

# ===== INCLUIR ROUTER DE AUTENTICACIÓN PRIMERO =====
app.include_router(auth_router)

# ===== ROUTERS EXISTENTES (Todos ahora protegidos automáticamente) =====
app.include_router(clientes.router)
app.include_router(insumos.router)
app.include_router(proveedores.router)
app.include_router(productos.router)
app.include_router(producto_insumo.router)
app.include_router(ventas.router)
app.include_router(importar_falabella.router)
app.include_router(importar_cencosud.router)
app.include_router(importar_walmart.router)
app.include_router(importar_ripley.router)
app.include_router(importar_hites.router)
app.include_router(manual.router)
app.include_router(produccion.router)
app.include_router(trabajadores.router)
app.include_router(ventas_maestra.router)
app.include_router(dashboard.router)
app.include_router(usuarios.router)
app.include_router(configuracion.router)
app.include_router(usuarios_jinja.router)
app.include_router(trabajadores_jinja.router)
app.include_router(camaras.router)


# Routers de configuración
app.include_router(config_clientes.router)
app.include_router(config_insumos.router)
app.include_router(config_proveedores.router)

app.include_router(trabajadores_acciones.router)
app.include_router(usuarios_acciones.router)

# Routers de logistica
app.include_router(devoluciones.router)
app.include_router(facturas.router)

# Routers de Finanzas
app.include_router(finanzas.router)

# Routers de E-commerce
app.include_router(ecomerce.router)
app.include_router(image_router.router)