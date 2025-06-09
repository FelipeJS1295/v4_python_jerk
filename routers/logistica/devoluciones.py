from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql
from datetime import datetime
import os
import shutil
from fastapi import Query

router = APIRouter(prefix="/logistica/devoluciones", tags=["Logística - Devoluciones"])
templates = Jinja2Templates(directory="templates")

# Ruta para mostrar la tabla de devoluciones
@router.get("/", response_class=HTMLResponse)
def vista_devoluciones(
    request: Request,
    numero_orden: str = Query(None),
    courier: str = Query(None),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    # Construir filtro dinámico
    condiciones = []
    valores = []

    if numero_orden:
        condiciones.append("d.numero_orden LIKE %s")
        valores.append(f"%{numero_orden}%")

    if courier:
        condiciones.append("d.courier LIKE %s")
        valores.append(f"%{courier}%")

    if fecha_inicio and fecha_fin:
        condiciones.append("d.fecha_devolucion BETWEEN %s AND %s")
        valores.extend([fecha_inicio, fecha_fin])

    filtro_sql = " AND ".join(condiciones)
    if filtro_sql:
        filtro_sql = "WHERE " + filtro_sql

    # Consulta principal
    query = f"""
        SELECT 
        d.*, 
        v.producto, 
        c.nombre AS cliente_nombre, 
        v.precio 
        FROM devoluciones d
        JOIN ventas_retail v ON d.venta_id = v.id
        JOIN clientes c ON v.cliente_id = c.id
        {filtro_sql}
        ORDER BY d.fecha_devolucion DESC
    """
    cursor.execute(query, tuple(valores))
    devoluciones = cursor.fetchall()

    # Totales
    total_venta = sum(d["precio"] or 0 for d in devoluciones)
    total_indemnizacion = sum(d["monto_indemnizacion"] or 0 for d in devoluciones)

    return templates.TemplateResponse("logistica/devoluciones/index.html", {
        "request": request,
        "devoluciones": devoluciones,
        "filtros": {
            "numero_orden": numero_orden,
            "courier": courier,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin
        },
        "total_venta": total_venta,
        "total_indemnizacion": total_indemnizacion
    })

# Ruta para formulario de nueva devolución
@router.get("/nueva", response_class=HTMLResponse)
def formulario_devolucion(request: Request):
    return templates.TemplateResponse("logistica/devoluciones/create.html", {
        "request": request,
        "estado_busqueda": None
    })

# Verificar si existe orden
@router.get("/buscar-orden", response_class=JSONResponse)
def buscar_orden(numero_orden: str):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM ventas_retail WHERE numero_orden = %s", (numero_orden,))
    venta = cursor.fetchone()
    cursor.close()
    conn.close()

    if venta:
        return {"existe": True, "venta_id": venta["id"]}
    else:
        return {"existe": False}

# Guardar nueva devolución
@router.post("/crear", response_class=RedirectResponse)
async def crear_devolucion(
    request: Request,
    venta_id: int = Form(...),
    numero_orden: str = Form(...),
    fecha_devolucion: str = Form(...),
    detalles: str = Form(...),
    courier: str = Form(...),
    observaciones: str = Form(None),
    fotos: UploadFile = File(None)
):
    ruta_foto = ""
    if fotos:
        carpeta = "static/uploads/devoluciones"
        os.makedirs(carpeta, exist_ok=True)
        nombre_archivo = f"{datetime.now().timestamp()}_{fotos.filename}"
        ruta_archivo = os.path.join(carpeta, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            shutil.copyfileobj(fotos.file, f)
        ruta_foto = ruta_archivo

    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO devoluciones (venta_id, numero_orden, fecha_devolucion, detalles, fotos, courier, observaciones)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        venta_id, numero_orden, fecha_devolucion, detalles, ruta_foto, courier, observaciones
    ))
    # Actualizar estado de la venta
    cursor.execute("UPDATE ventas_retail SET estado = 'devolucion' WHERE id = %s", (venta_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/logistica/devoluciones", status_code=303)

@router.get("/{id}/ver", response_class=HTMLResponse)
def ver_devolucion(id: int, request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.*, v.producto, v.numero_orden, c.nombre AS cliente_nombre, v.precio
        FROM devoluciones d
        JOIN ventas_retail v ON d.venta_id = v.id
        JOIN clientes c ON v.cliente_id = c.id
        WHERE d.id = %s
    """, (id,))
    devolucion = cursor.fetchone()
    cursor.close()
    conn.close()

    if not devolucion:
        return HTMLResponse("Devolución no encontrada", status_code=404)

    return templates.TemplateResponse("logistica/devoluciones/show.html", {
        "request": request,
        "d": devolucion
    })

@router.get("/{id}/editar", response_class=HTMLResponse)
def editar_devolucion(id: int, request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM devoluciones WHERE id = %s", (id,))
    d = cursor.fetchone()
    cursor.close()
    conn.close()

    return templates.TemplateResponse("logistica/devoluciones/edit.html", {
        "request": request,
        "d": d
    })

@router.post("/{id}/editar", response_class=RedirectResponse)
async def actualizar_devolucion(
    id: int,
    fecha_devolucion: str = Form(...),
    courier: str = Form(...),
    observaciones: str = Form(None),
    monto_indemnizacion: float = Form(None)
):
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE devoluciones 
        SET fecha_devolucion=%s, courier=%s, observaciones=%s, monto_indemnizacion=%s
        WHERE id = %s
    """, (
        fecha_devolucion, courier, observaciones, monto_indemnizacion, id
    ))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/logistica/devoluciones", status_code=303)

@router.post("/{id}/eliminar", response_class=RedirectResponse)
def eliminar_devolucion(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    # Obtener venta_id para actualizar el estado de la venta
    cursor.execute("SELECT venta_id FROM devoluciones WHERE id = %s", (id,))
    row = cursor.fetchone()
    if row:
        venta_id = row["venta_id"]
        cursor.execute("UPDATE ventas_retail SET estado = 'nueva' WHERE id = %s", (venta_id,))
        cursor.execute("DELETE FROM devoluciones WHERE id = %s", (id,))
        conn.commit()

    cursor.close()
    conn.close()
    return RedirectResponse(url="/logistica/devoluciones", status_code=303)