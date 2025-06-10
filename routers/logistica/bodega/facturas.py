from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql
from datetime import datetime

router = APIRouter(prefix="/bodega/facturas", tags=["Bodega - Facturas"])
templates = Jinja2Templates(directory="templates")

# =========================
# VISTA: Lista de facturas
# =========================
@router.get("/", response_class=HTMLResponse)
def listar_facturas(
    request: Request,
    estado: str = None,
    proveedor: str = None,
    numero: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    condiciones = []
    valores = []

    if estado:
        condiciones.append("f.estado = %s")
        valores.append(estado)
    if proveedor:
        condiciones.append("p.nombre LIKE %s")
        valores.append(f"%{proveedor}%")
    if numero:
        condiciones.append("f.numero_documento LIKE %s")
        valores.append(f"%{numero}%")
    if fecha_desde:
        condiciones.append("f.fecha_documento >= %s")
        valores.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("f.fecha_documento <= %s")
        valores.append(fecha_hasta)

    where_clause = " AND ".join(condiciones)
    sql = """
        SELECT f.*, p.nombre AS proveedor 
        FROM facturas_compra f
        JOIN proveedores p ON f.proveedor_id = p.id
    """
    if where_clause:
        sql += " WHERE " + where_clause
    sql += " ORDER BY f.fecha_documento DESC"

    cursor.execute(sql, tuple(valores))
    facturas = cursor.fetchall()

    return templates.TemplateResponse("bodega/facturas/index.html", {
        "request": request,
        "facturas": facturas,
        "estado_seleccionado": estado or "",
        "proveedor_busqueda": proveedor or "",
        "numero_busqueda": numero or "",
        "fecha_desde": fecha_desde or "",
        "fecha_hasta": fecha_hasta or ""
    })

# =========================
# VISTA: Crear nueva factura
# =========================
@router.get("/crear", response_class=HTMLResponse)
def crear_factura_form(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre ASC")
    proveedores = cursor.fetchall()

    cursor.execute("SELECT id, nombre, precio_costo FROM insumos ORDER BY nombre ASC")
    insumos = cursor.fetchall()

    return templates.TemplateResponse("bodega/facturas/create.html", {
        "request": request,
        "proveedores": proveedores,
        "insumos": insumos
    })

# =========================
# ENDPOINT: Guardar factura
# =========================
@router.post("/guardar")
async def guardar_factura(
    request: Request,
    proveedor_id: int = Form(...),
    numero_documento: str = Form(...),
    fecha_documento: str = Form(...),
    fecha_vencimiento: str = Form(...),
    insumo_ids: list[int] = Form(...),
    cantidades: list[float] = Form(...),
    precios_unitarios: list[float] = Form(...),
    estado: str = Form("pendiente")
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    neto = sum(c * p for c, p in zip(cantidades, precios_unitarios))
    iva = round(neto * 0.19, 2)
    total = round(neto + iva, 2)

    cursor.execute("""
        INSERT INTO facturas_compra (proveedor_id, numero_documento, fecha_documento, fecha_vencimiento, neto, iva, total, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (proveedor_id, numero_documento, fecha_documento, fecha_vencimiento, neto, iva, total, estado))

    factura_id = cursor.lastrowid

    for insumo_id, cantidad, precio_unitario in zip(insumo_ids, cantidades, precios_unitarios):
        cursor.execute("""
            INSERT INTO factura_insumos (factura_id, insumo_id, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s)
        """, (factura_id, insumo_id, cantidad, precio_unitario))

    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/bodega/facturas", status_code=303)


@router.get("/show/{id}", response_class=HTMLResponse)
def ver_factura(id: int, request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT f.*, p.nombre AS proveedor 
        FROM facturas_compra f
        JOIN proveedores p ON f.proveedor_id = p.id
        WHERE f.id = %s
    """, (id,))
    factura = cursor.fetchone()

    cursor.execute("""
        SELECT fi.*, i.nombre 
        FROM factura_insumos fi
        JOIN insumos i ON fi.insumo_id = i.id
        WHERE fi.factura_id = %s
    """, (id,))
    insumos = cursor.fetchall()

    return templates.TemplateResponse("bodega/facturas/show.html", {
        "request": request,
        "factura": factura,
        "insumos": insumos
    })
    
@router.get("/editar/{id}", response_class=HTMLResponse)
def editar_factura(id: int, request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre ASC")
    proveedores = cursor.fetchall()

    cursor.execute("SELECT * FROM facturas_compra WHERE id = %s", (id,))
    factura = cursor.fetchone()

    cursor.execute("""
        SELECT fi.*, i.nombre 
        FROM factura_insumos fi
        JOIN insumos i ON fi.insumo_id = i.id
        WHERE fi.factura_id = %s
    """, (id,))
    insumos = cursor.fetchall()

    cursor.execute("SELECT id, nombre FROM insumos ORDER BY nombre ASC")
    lista_insumos = cursor.fetchall()

    return templates.TemplateResponse("bodega/facturas/edit.html", {
        "request": request,
        "factura": factura,
        "insumos": insumos,
        "proveedores": proveedores,
        "lista_insumos": lista_insumos
    })

@router.post("/actualizar/{id}")
def actualizar_factura(
    id: int,
    proveedor_id: int = Form(...),
    numero_documento: str = Form(...),
    fecha_documento: str = Form(...),
    fecha_vencimiento: str = Form(...),
    insumo_ids: list[int] = Form(...),
    cantidades: list[float] = Form(...),
    precios_unitarios: list[float] = Form(...),
    estado: str = Form(...)
):
    conn = conectar_mysql()
    cursor = conn.cursor()

    neto = sum(c * p for c, p in zip(cantidades, precios_unitarios))
    iva = round(neto * 0.19, 2)
    total = round(neto + iva, 2)

    cursor.execute("""
        UPDATE facturas_compra
        SET proveedor_id=%s, numero_documento=%s, fecha_documento=%s, fecha_vencimiento=%s,
            neto=%s, iva=%s, total=%s, estado=%s
        WHERE id=%s
    """, (proveedor_id, numero_documento, fecha_documento, fecha_vencimiento, neto, iva, total, id, estado))

    # Eliminar detalle anterior
    cursor.execute("DELETE FROM factura_insumos WHERE factura_id = %s", (id,))

    # Insertar nuevo detalle
    for insumo_id, cantidad, precio_unitario in zip(insumo_ids, cantidades, precios_unitarios):
        cursor.execute("""
            INSERT INTO factura_insumos (factura_id, insumo_id, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s)
        """, (id, insumo_id, cantidad, precio_unitario))

    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/bodega/facturas", status_code=303)

@router.get("/eliminar/{id}")
def eliminar_factura(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM facturas_compra WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse(url="/bodega/facturas", status_code=303)