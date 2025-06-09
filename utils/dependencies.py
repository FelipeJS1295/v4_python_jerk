from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from db import conectar_mysql
from utils.auth import obtener_usuario_actual

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session_token: Optional[str] = Cookie(None)
):
    """Dependencia para obtener el usuario actual"""
    
    # Priorizar token de Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    elif session_token:
        token = session_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    conn = conectar_mysql()
    try:
        user = obtener_usuario_actual(token, conn)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    finally:
        conn.close()

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependencia para usuario activo"""
    if not current_user.get("activo"):
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user

def require_roles(allowed_roles: list):
    """Decorator para requerir roles específicos"""
    def role_checker(current_user: dict = Depends(get_current_active_user)):
        if current_user.get("rol") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes"
            )
        return current_user
    return role_checker