from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from db import conectar_mysql
from utils.auth import hashear_contraseña
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion/usuarios/nuevo", response_class=HTMLResponse)
def nuevo_usuario(request: Request):
    return templates.TemplateResponse("configuracion/usuarios/create.html", {"request": request})

# Crear usuario (POST desde create.html)
@router.post("/configuracion/usuarios/crear")
def crear_usuario(
    nombre_usuario: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
    activo: int = Form(...)
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El email ya está registrado")

        contraseña_hash = hashear_contraseña(password)

        cursor.execute("""
            INSERT INTO users (nombre_usuario, email, password, rol, activo)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombre_usuario, email, contraseña_hash, rol, activo))
        conn.commit()

        return RedirectResponse(url="/configuracion/usuarios", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear usuario: {str(e)}")
    finally:
        cursor.close()
        conn.close()


# Cargar usuario para edición
@router.get("/configuracion/usuarios/{usuario_id}/editar")
def cargar_usuario_editar(request: Request, usuario_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (usuario_id,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return templates.TemplateResponse("configuracion/usuarios/edit.html", {
            "request": request,
            "usuario": usuario
        })

    finally:
        cursor.close()
        conn.close()


# Actualizar usuario (POST desde edit.html)
@router.post("/configuracion/usuarios/{usuario_id}/actualizar")
def actualizar_usuario(
    usuario_id: int,
    nombre_usuario: str = Form(...),
    email: str = Form(...),
    rol: str = Form(...),
    activo: int = Form(...)
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE users SET nombre_usuario = %s, email = %s, rol = %s, activo = %s
            WHERE id = %s
        """, (nombre_usuario, email, rol, activo, usuario_id))
        conn.commit()

        return RedirectResponse(url="/configuracion/usuarios", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar usuario: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/configuracion/usuarios/{usuario_id}/eliminar")
def eliminar_usuario(usuario_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (usuario_id,))
        conn.commit()
        return RedirectResponse(url="/configuracion/usuarios", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")
    finally:
        cursor.close()
        conn.close()
