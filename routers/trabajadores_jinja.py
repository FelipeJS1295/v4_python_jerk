from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion/trabajadores", response_class=HTMLResponse)
def vista_trabajadores(request: Request):
    """Vista Jinja2 para gestionar trabajadores"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT t.*, u.rol
            FROM trabajadores t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC
        """)
        trabajadores = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    
    return templates.TemplateResponse("configuracion/trabajadores.html", {
        "request": request,
        "trabajadores": trabajadores
    })
