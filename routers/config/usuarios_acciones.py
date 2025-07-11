from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from db import conectar_mysql
from utils.auth import hashear_contraseña
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import Optional

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
        # Verificar si el email ya existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El email ya está registrado")

        # Hashear la contraseña
        contraseña_hash = hashear_contraseña(password)

        # Insertar el nuevo usuario
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


# Actualizar usuario (POST desde edit.html) - CON SOPORTE PARA CONTRASEÑA OPCIONAL
@router.post("/configuracion/usuarios/{usuario_id}/actualizar")
def actualizar_usuario(
    usuario_id: int,
    nombre_usuario: str = Form(...),
    email: str = Form(...),
    rol: str = Form(...),
    activo: int = Form(...),
    password: Optional[str] = Form(None)  # Contraseña opcional
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    try:
        # Verificar si el email ya existe en otro usuario
        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, usuario_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El email ya está siendo usado por otro usuario")

        # Si se proporciona una nueva contraseña, actualizarla también
        if password and password.strip():
            contraseña_hash = hashear_contraseña(password)
            cursor.execute("""
                UPDATE users 
                SET nombre_usuario = %s, email = %s, password = %s, rol = %s, activo = %s
                WHERE id = %s
            """, (nombre_usuario, email, contraseña_hash, rol, activo, usuario_id))
        else:
            # Solo actualizar los demás campos, mantener la contraseña actual
            cursor.execute("""
                UPDATE users 
                SET nombre_usuario = %s, email = %s, rol = %s, activo = %s
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
        # Verificar que el usuario existe antes de eliminar
        cursor.execute("SELECT id FROM users WHERE id = %s", (usuario_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        cursor.execute("DELETE FROM users WHERE id = %s", (usuario_id,))
        conn.commit()
        
        return RedirectResponse(url="/configuracion/usuarios", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar usuario: {str(e)}")
    finally:
        cursor.close()
        conn.close()