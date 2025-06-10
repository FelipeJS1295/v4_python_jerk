
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
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
)

from routers.logistica import devoluciones
from routers.logistica.bodega import facturas

# Routers de configuración
from routers.config import (
    clientes as config_clientes,
    insumos as config_insumos,
    proveedores as config_proveedores,
    productos as config_productos,
)

from routers.auth import router as auth_router

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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ===== RUTA RAÍZ CON AUTENTICACIÓN =====
@app.get("/")
def home(request: Request):
    """Redirigir a login o dashboard según autenticación"""
    
    # Verificar si ya está autenticado
    token = request.cookies.get("session_token")
    
    if token:
        from utils.auth import verificar_token
        from db import conectar_mysql
        
        payload = verificar_token(token)
        
        if payload:
            # Verificar que sea admin
            conn = conectar_mysql()
            cursor = conn.cursor(dictionary=True)
            
            try:
                user_id = payload.get("sub")
                cursor.execute("""
                    SELECT * FROM users 
                    WHERE id = %s AND activo = 1 AND rol = 'Admin'
                """, (user_id,))
                user = cursor.fetchone()
                
                if user:
                    # Ya autenticado, ir al dashboard
                    return templates.TemplateResponse("dashboard.html", {
                        "request": request,
                        "usuario": user
                    })
                    
            finally:
                cursor.close()
                conn.close()
    
    # No autenticado, mostrar login
    return templates.TemplateResponse("auth/login.html", {"request": request})

# ===== FUNCIÓN HELPER PARA PROTEGER RUTAS =====
def verificar_admin_main(request: Request):
    """Función helper para verificar que el usuario es admin"""
    from fastapi import HTTPException
    from utils.auth import verificar_token
    from db import conectar_mysql
    
    token = request.cookies.get("session_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    payload = verificar_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        user_id = payload.get("sub")
        cursor.execute("""
            SELECT * FROM users 
            WHERE id = %s AND activo = 1 AND rol = 'Admin'
        """, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Solo administradores")
        
        return user
        
    finally:
        cursor.close()
        conn.close()

# ===== RUTAS PROTEGIDAS DE EJEMPLO =====
@app.get("/dashboard-main")
def dashboard_main(request: Request):
    """Dashboard principal protegido"""
    usuario = verificar_admin_main(request)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": usuario
    })

# ===== INCLUIR ROUTER DE AUTENTICACIÓN =====
app.include_router(auth_router)

# ===== ROUTERS EXISTENTES =====
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

# Routers de configuración
app.include_router(config_clientes.router)
app.include_router(config_insumos.router)
app.include_router(config_proveedores.router)
app.include_router(config_productos.router)

# Routers de logistica
app.include_router(devoluciones.router)
app.include_router(facturas.router)