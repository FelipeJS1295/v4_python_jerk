from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql
from schemas.usuario_schema import UsuarioLogin
from utils.auth import verificar_contraseña, crear_token
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["Autenticación"])
templates = Jinja2Templates(directory="templates")

# ===== VISTA LOGIN =====
@router.get("/login", response_class=HTMLResponse)
async def vista_login(request: Request):
    """Vista del formulario de login"""
    return templates.TemplateResponse("auth/login.html", {"request": request})

# ===== ENDPOINT LOGIN =====
@router.post("/login")
async def login(datos: UsuarioLogin, response: Response):
    """Iniciar sesión - SOLO ADMINISTRADORES"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar usuario por email Y verificar que sea Admin
        cursor.execute("""
            SELECT * FROM users 
            WHERE email = %s AND activo = 1 AND rol = 'Admin'
        """, (datos.email,))
        user = cursor.fetchone()

        if not user or not verificar_contraseña(datos.password, user["password"]):
            raise HTTPException(
                status_code=401, 
                detail="Acceso denegado. Solo administradores autorizados."
            )

        # Crear token
        token_data = {"sub": str(user["id"])}
        token = crear_token(token_data, timedelta(hours=8))
        
        # Configurar cookie segura
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=False,  # Cambiar a True en producción
            samesite="lax",
            max_age=8*60*60  # 8 horas
        )
        
        return {
            "mensaje": "Acceso autorizado",
            "usuario": {
                "id": user["id"],
                "nombre_usuario": user["nombre_usuario"],
                "rol": user["rol"]
            }
        }
        
    finally:
        cursor.close()
        conn.close()

# ===== ENDPOINT LOGOUT =====
@router.post("/logout")
async def logout(response: Response):
    """Cerrar sesión"""
    response.delete_cookie(key="session_token")
    return {"mensaje": "Sesión cerrada"}

# ===== VERIFICAR SESIÓN =====
@router.get("/verificar-sesion")
async def verificar_sesion(request: Request):
    """Verificar si hay una sesión activa de admin"""
    token = request.cookies.get("session_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    from utils.auth import verificar_token
    payload = verificar_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    # Verificar que el usuario sigue siendo admin activo
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
            raise HTTPException(status_code=401, detail="Usuario no autorizado")
        
        return {
            "valid": True,
            "usuario": {
                "id": user["id"],
                "nombre_usuario": user["nombre_usuario"],
                "rol": user["rol"]
            }
        }
        
    finally:
        cursor.close()
        conn.close()

# ===== DASHBOARD =====
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard - Solo para administradores autenticados"""
    
    # Verificar sesión
    token = request.cookies.get("session_token")
    if not token:
        return templates.TemplateResponse("auth/login.html", {"request": request})
    
    from utils.auth import verificar_token
    payload = verificar_token(token)
    
    if not payload:
        return templates.TemplateResponse("auth/login.html", {"request": request})
    
    # Verificar usuario admin
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
            return templates.TemplateResponse("auth/login.html", {"request": request})
        
        # Redirigir al dashboard principal (raíz)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
        
    finally:
        cursor.close()
        conn.close()

# ===== FUNCIÓN HELPER PARA PROTEGER RUTAS =====
def verificar_admin(request: Request):
    """Función helper para verificar que el usuario es admin"""
    token = request.cookies.get("session_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    from utils.auth import verificar_token
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

# ===== REDIRECCIÓN RAÍZ =====
@router.get("/")
async def root(request: Request):
    """Redireccionar a login o dashboard según autenticación"""
    
    # Verificar si ya está autenticado
    token = request.cookies.get("session_token")
    
    if token:
        from utils.auth import verificar_token
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