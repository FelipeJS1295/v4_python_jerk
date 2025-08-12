from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import conectar_mysql
from schemas.usuario_schema import UsuarioLogin
from utils.auth import hashear_contraseña, verificar_contraseña, crear_token, verificar_token
from datetime import timedelta
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import jwt
from typing import Optional

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
templates = Jinja2Templates(directory="templates")
security = HTTPBearer(auto_error=False)

def obtener_usuario_actual(request: Request) -> Optional[dict]:
    """Obtener usuario actual desde el token en cookies o headers"""
    try:
        # Intentar obtener token desde cookies
        token = request.cookies.get("access_token")
        
        # Si no hay en cookies, intentar desde headers
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            return None
        
        # Verificar y decodificar token
        payload = verificar_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Obtener datos del usuario desde la base de datos
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT id, nombre_usuario, email, rol, activo 
                FROM users 
                WHERE id = %s AND activo = 1
            """, (user_id,))
            
            usuario = cursor.fetchone()
            return usuario
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Error obteniendo usuario actual: {str(e)}")
        return None

@router.get("/verificar-sesion")
async def verificar_sesion(request: Request):
    """Verificar si la sesión del usuario es válida"""
    try:
        usuario = obtener_usuario_actual(request)
        
        if usuario:
            return {
                "valid": True,
                "usuario": {
                    "id": usuario.get("id"),
                    "nombre_usuario": usuario.get("nombre_usuario"),
                    "email": usuario.get("email"),
                    "rol": usuario.get("rol")
                }
            }
        else:
            return {
                "valid": False,
                "usuario": None
            }
            
    except Exception as e:
        print(f"Error en verificar_sesion: {str(e)}")
        return {
            "valid": False,
            "usuario": None,
            "error": str(e)
        }

@router.post("/login")
def login(datos: UsuarioLogin):
    """Login de usuario - SOLO ADMINISTRADORES"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar usuario por email Y verificar que sea Admin y esté activo
        cursor.execute("""
            SELECT * FROM users 
            WHERE email = %s AND activo = 1 AND rol = 'Admin'
        """, (datos.email,))
        user = cursor.fetchone()

        if not user or not verificar_contraseña(datos.password, user["password"]):
            raise HTTPException(status_code=401, detail="Credenciales inválidas o acceso denegado")

        # Crear token
        token = crear_token({"sub": str(user["id"])}, timedelta(hours=8))
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "usuario": {
                "id": user["id"],
                "nombre_usuario": user["nombre_usuario"],
                "rol": user["rol"]
            }
        }
        
    finally:
        cursor.close()
        conn.close()

@router.post("/logout")
async def logout():
    """Cerrar sesión del usuario"""
    try:
        response = JSONResponse(content={"message": "Sesión cerrada exitosamente"})
        response.delete_cookie("access_token")
        return response
    except Exception as e:
        return JSONResponse(
            content={"message": "Error al cerrar sesión", "error": str(e)},
            status_code=500
        )

@router.get("/listar")
def listar_usuarios():
    """Listar todos los usuarios"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nombre_usuario, email, rol, activo, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        usuarios = cursor.fetchall()
        
        return {"usuarios": usuarios}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener usuarios: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.delete("/eliminar/{usuario_id}")
def eliminar_usuario(usuario_id: int):
    """Eliminar usuario por ID"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verificar que el usuario existe
        cursor.execute("SELECT id FROM users WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Eliminar usuario
        cursor.execute("DELETE FROM users WHERE id = %s", (usuario_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        return {"mensaje": "Usuario eliminado correctamente"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.put("/cambiar-estado/{usuario_id}")
def cambiar_estado_usuario(usuario_id: int):
    """Cambiar estado activo/inactivo de un usuario"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener estado actual
        cursor.execute("SELECT activo FROM users WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Cambiar estado
        nuevo_estado = 0 if usuario["activo"] == 1 else 1
        cursor.execute("UPDATE users SET activo = %s WHERE id = %s", (nuevo_estado, usuario_id))
        conn.commit()
        
        return {"mensaje": f"Usuario {'activado' if nuevo_estado else 'desactivado'} correctamente"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al cambiar estado: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/stats")
def estadisticas_usuarios():
    """Estadísticas básicas de usuarios"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Total de usuarios
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total = cursor.fetchone()["total"]
        
        # Usuarios activos
        cursor.execute("SELECT COUNT(*) as activos FROM users WHERE activo = 1")
        activos = cursor.fetchone()["activos"]
        
        # Usuarios por rol
        cursor.execute("SELECT rol, COUNT(*) as cantidad FROM users GROUP BY rol")
        por_rol = cursor.fetchall()
        
        return {
            "total_usuarios": total,
            "usuarios_activos": activos,
            "usuarios_inactivos": total - activos,
            "usuarios_por_rol": por_rol
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/verificar/{email}")
def verificar_email(email: str):
    """Verificar si un email ya está registrado"""
    conn = conectar_mysql()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existe = cursor.fetchone() is not None
        
        return {"email": email, "existe": existe}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar email: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/configuracion/usuarios", response_class=HTMLResponse)
def vista_usuarios(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, nombre_usuario, email, rol, activo, created_at FROM users ORDER BY created_at DESC")
        usuarios = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    
    return templates.TemplateResponse("configuracion/usuarios.html", {"request": request, "usuarios": usuarios})