from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from db import conectar_mysql
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/configuracion/trabajadores/nuevo", response_class=HTMLResponse)
def nuevo_trabajador(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, nombre_usuario, email FROM users WHERE activo = 1 ORDER BY nombre_usuario")
        usuarios = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return templates.TemplateResponse("configuracion/trabajadores/create.html", {
        "request": request,
        "usuarios": usuarios
    })

# Crear trabajador (POST desde create.html)
@router.post("/configuracion/trabajadores/crear")
def crear_trabajador(
    user_id: int = Form(None),  # Agregado este parámetro
    nombres: str = Form(...),
    apellidos: str = Form(...),
    rut: str = Form(...),
    telefono: str = Form(""),
    direccion: str = Form(""),
    afp: str = Form(""),
    salud: str = Form(""),
    sueldo: float = Form(0),
    fecha_ingreso: str = Form(""),
    talla_polera: str = Form(""),
    talla_pantalon: str = Form(""),
    talla_zapatos: str = Form(""),
    banco: str = Form(""),
    tipo_cuenta: str = Form(""),
    numero_cuenta: str = Form(""),
    estado: str = Form("activo")
):
    conn = conectar_mysql()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO trabajadores 
            (user_id, nombres, apellidos, rut, telefono, direccion, afp, salud, sueldo, fecha_ingreso, 
             talla_polera, talla_pantalon, talla_zapatos, banco, tipo_cuenta, numero_cuenta, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, nombres, apellidos, rut, telefono, direccion, afp, salud, sueldo, fecha_ingreso,
            talla_polera, talla_pantalon, talla_zapatos, banco, tipo_cuenta, numero_cuenta, estado
        ))
        conn.commit()
        return RedirectResponse(url="/configuracion/trabajadores", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear trabajador: {str(e)}")
    finally:
        cursor.close()
        conn.close()


# Editar trabajador (GET para cargar en formulario)
@router.get("/configuracion/trabajadores/{trabajador_id}/editar")
def cargar_edicion_trabajador(request: Request, trabajador_id: int):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM trabajadores WHERE id = %s", (trabajador_id,))
        trabajador = cursor.fetchone()
        if not trabajador:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")

        # Obtener usuarios disponibles para el select
        cursor.execute("SELECT id, nombre_usuario, email FROM users WHERE activo = 1 ORDER BY nombre_usuario")
        usuarios = cursor.fetchall()

        return templates.TemplateResponse("configuracion/trabajadores/edit.html", {
            "request": request,
            "trabajador": trabajador,
            "usuarios": usuarios
        })

    finally:
        cursor.close()
        conn.close()


# Actualizar trabajador (POST desde edit.html)
@router.post("/configuracion/trabajadores/{trabajador_id}/actualizar")
def actualizar_trabajador(
    trabajador_id: int,
    user_id: int = Form(None),  # Agregado este parámetro
    nombres: str = Form(...),
    apellidos: str = Form(...),
    rut: str = Form(...),
    telefono: str = Form(""),
    direccion: str = Form(""),
    afp: str = Form(""),
    salud: str = Form(""),
    sueldo: float = Form(0),
    fecha_ingreso: str = Form(""),
    talla_polera: str = Form(""),
    talla_pantalon: str = Form(""),
    talla_zapatos: str = Form(""),
    banco: str = Form(""),
    tipo_cuenta: str = Form(""),
    numero_cuenta: str = Form(""),
    estado: str = Form("activo")
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE trabajadores SET 
                user_id=%s, nombres=%s, apellidos=%s, rut=%s, telefono=%s, direccion=%s,
                afp=%s, salud=%s, sueldo=%s, fecha_ingreso=%s,
                talla_polera=%s, talla_pantalon=%s, talla_zapatos=%s,
                banco=%s, tipo_cuenta=%s, numero_cuenta=%s, estado=%s
            WHERE id=%s
        """, (
            user_id, nombres, apellidos, rut, telefono, direccion,
            afp, salud, sueldo, fecha_ingreso,
            talla_polera, talla_pantalon, talla_zapatos,
            banco, tipo_cuenta, numero_cuenta, estado,
            trabajador_id
        ))
        conn.commit()
        return RedirectResponse(url="/configuracion/trabajadores", status_code=303)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar trabajador: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/configuracion/trabajadores/{trabajador_id}/eliminar")
def eliminar_trabajador(trabajador_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM trabajadores WHERE id = %s", (trabajador_id,))
        conn.commit()
        return RedirectResponse(url="/configuracion/trabajadores", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar trabajador: {str(e)}")
    finally:
        cursor.close()
        conn.close()