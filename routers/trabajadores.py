from fastapi import APIRouter, Request, HTTPException
from db import conectar_mysql
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/trabajadores", tags=["Trabajadores"])
templates = Jinja2Templates(directory="templates")

@router.get("/")
def listar_trabajadores():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombres FROM trabajadores")
    resultado = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultado

@router.get("/configuracion/trabajadores", response_class=HTMLResponse)
def vista_trabajadores(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.*, u.rol FROM trabajadores t
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

@router.delete("/{trabajador_id}")
def eliminar_trabajador(trabajador_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    
    try:
        # Verificar si el trabajador existe
        cursor.execute("SELECT id FROM trabajadores WHERE id = %s", (trabajador_id,))
        trabajador = cursor.fetchone()
        
        if not trabajador:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")
        
        # Eliminar el trabajador
        cursor.execute("DELETE FROM trabajadores WHERE id = %s", (trabajador_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se pudo eliminar el trabajador")
        
        return {"message": "Trabajador eliminado exitosamente"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar trabajador: {str(e)}")
    finally:
        cursor.close()
        conn.close()