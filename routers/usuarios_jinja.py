from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion/usuarios", response_class=HTMLResponse)
def vista_usuarios(request: Request):
    """Vista Jinja2 para gestionar usuarios"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, nombre_usuario, email, rol, activo, created_at FROM users ORDER BY created_at DESC")
        usuarios = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    
    return templates.TemplateResponse("configuracion/usuarios.html", {
        "request": request,
        "usuarios": usuarios
    })
