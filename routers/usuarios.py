from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from db import conectar_mysql
from schemas.usuario_schema import UsuarioLogin
from utils.auth import hashear_contraseña, verificar_contraseña, crear_token
from datetime import timedelta

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

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