from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
from db import conectar_mysql
from datetime import date, timedelta
from typing import Optional

router = APIRouter(prefix="/finanzas", tags=["Finanzas"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Calcular días vencido
def calcular_dias_vencido(fecha_vencimiento):
    hoy = date.today()
    if fecha_vencimiento < hoy:
        return (hoy - fecha_vencimiento).days
    return 0

# Función para calcular faltante de una factura (SOLO ENTEROS)
def calcular_faltante_factura(cursor, factura_id, total_factura):
    cursor.execute(
        "SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", 
        (factura_id,)
    )
    resultado = cursor.fetchone()
    total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
    faltante = int(total_factura) - total_pagado
    return max(0, faltante)  # Siempre retorna entero, no negativo

# Mostrar listado de facturas con filtros
@router.get("/", response_class=HTMLResponse)
def listar_facturas(
    request: Request,
    proveedor: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    monto_min: Optional[int] = Query(None),  # Cambié a int
    monto_max: Optional[int] = Query(None),  # Cambié a int
    orden: Optional[str] = Query("fecha_vencimiento_asc")
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    # Query base
    query = """
        SELECT fc.id, p.nombre AS proveedor, fc.fecha_documento, fc.fecha_vencimiento, fc.total
        FROM facturas_compra fc
        JOIN proveedores p ON fc.proveedor_id = p.id
        WHERE 1=1
    """
    params = []
    
    # Filtro por proveedor
    if proveedor:
        query += " AND p.nombre LIKE %s"
        params.append(f"%{proveedor}%")
    
    # Filtro por fechas
    if fecha_desde:
        query += " AND fc.fecha_vencimiento >= %s"
        params.append(fecha_desde)
    
    if fecha_hasta:
        query += " AND fc.fecha_vencimiento <= %s"
        params.append(fecha_hasta)
    
    # Filtro por montos
    if monto_min:
        query += " AND fc.total >= %s"
        params.append(monto_min)
    
    if monto_max:
        query += " AND fc.total <= %s"
        params.append(monto_max)
    
    # Ordenamiento
    orden_map = {
        "fecha_vencimiento_asc": "fc.fecha_vencimiento ASC",
        "fecha_vencimiento_desc": "fc.fecha_vencimiento DESC",
        "monto_asc": "fc.total ASC",
        "monto_desc": "fc.total DESC",
        "proveedor": "p.nombre ASC"
    }
    
    if orden in orden_map:
        query += f" ORDER BY {orden_map[orden]}"
    else:
        query += " ORDER BY fc.fecha_vencimiento ASC"
    
    cursor.execute(query, params)
    facturas = cursor.fetchall()
    
    # Calcular días vencido, faltante y aplicar filtro de estado
    facturas_filtradas = []
    hoy = date.today()
    
    for f in facturas:
        f["dias_vencido"] = calcular_dias_vencido(f["fecha_vencimiento"])
        f["faltante"] = calcular_faltante_factura(cursor, f["id"], f["total"])
        f["total"] = int(f["total"])  # Asegurar que total sea entero
        
        # Filtro por estado
        if estado:
            if estado == "vencido" and f["dias_vencido"] <= 0:
                continue
            elif estado == "al_dia" and f["dias_vencido"] > 0:
                continue
            elif estado == "por_vencer":
                dias_hasta_vencimiento = (f["fecha_vencimiento"] - hoy).days
                if dias_hasta_vencimiento < 0 or dias_hasta_vencimiento > 7:
                    continue
            elif estado == "pagado" and f["faltante"] > 0:
                continue
            elif estado == "pendiente" and f["faltante"] <= 0:
                continue
        
        facturas_filtradas.append(f)
    
    # Calcular totales para el resumen
    total_facturas = len(facturas_filtradas)
    total_monto = sum(f["total"] for f in facturas_filtradas)
    total_faltante = sum(f["faltante"] for f in facturas_filtradas)
    
    cursor.close()
    conn.close()
    
    return templates.TemplateResponse("finanzas/index.html", {
        "request": request,
        "facturas": facturas_filtradas,
        "total_facturas": total_facturas,
        "total_monto": total_monto,
        "total_faltante": total_faltante
    })

# Mostrar detalle de factura (SOLO ENTEROS)
@router.get("/factura/{factura_id}", response_class=HTMLResponse)
def detalle_factura(request: Request, factura_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT fc.id, p.nombre AS proveedor, fc.fecha_documento, fc.fecha_vencimiento, fc.total
        FROM facturas_compra fc
        JOIN proveedores p ON fc.proveedor_id = p.id
        WHERE fc.id = %s
    """, (factura_id,))
    factura = cursor.fetchone()

    cursor.execute("SELECT * FROM pagos_factura WHERE factura_id = %s ORDER BY fecha ASC", (factura_id,))
    pagos = cursor.fetchall()

    # Trabajar SOLO con enteros
    total_pagado = sum(int(p["monto"]) for p in pagos)
    faltante = int(factura["total"]) - total_pagado
    faltante = max(0, faltante)  # No permitir negativos

    cursor.close()
    conn.close()

    return templates.TemplateResponse("finanzas/detalle_factura.html", {
        "request": request,
        "factura": factura,
        "pagos": pagos,
        "total_pagado": total_pagado,
        "faltante": faltante
    })

# Agregar pago (SOLO ENTEROS)
@router.post("/factura/{factura_id}/agregar-pago")
def agregar_pago(
    factura_id: int,
    tipo: str = Form(...),
    numero: str = Form(...),
    fecha: date = Form(...),
    monto: int = Form(...)
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener información de la factura
        cursor.execute("SELECT total FROM facturas_compra WHERE id = %s", (factura_id,))
        factura = cursor.fetchone()
        
        if not factura:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=factura_no_encontrada", status_code=303)
        
        # Calcular total pagado actual (ENTEROS)
        cursor.execute("SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", (factura_id,))
        resultado = cursor.fetchone()
        total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
        
        # Calcular faltante (ENTEROS)
        faltante = int(factura["total"]) - total_pagado
        
        # Validaciones
        if monto <= 0:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=monto_invalido", status_code=303)
        
        if monto > faltante:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=monto_excede_faltante", status_code=303)
        
        if not numero.strip():
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=numero_requerido", status_code=303)
        
        # Insertar el pago
        cursor.execute("""
            INSERT INTO pagos_factura (factura_id, tipo, numero, monto, fecha)
            VALUES (%s, %s, %s, %s, %s)
        """, (factura_id, tipo, numero.strip(), monto, fecha))
        
        # Calcular nuevo faltante después del pago
        nuevo_faltante = faltante - monto
        
        # Actualizar estado de la factura según el nuevo faltante
        if nuevo_faltante <= 0:
            nuevo_estado = "pagada"
        else:
            # Verificar si está vencida
            cursor.execute("SELECT fecha_vencimiento FROM facturas_compra WHERE id = %s", (factura_id,))
            fecha_venc = cursor.fetchone()["fecha_vencimiento"]
            dias_vencido = calcular_dias_vencido(fecha_venc)
            
            if dias_vencido > 0:
                nuevo_estado = "vencida"
            else:
                nuevo_estado = "pendiente"
        
        # Actualizar el estado en la base de datos
        cursor.execute("""
            UPDATE facturas_compra 
            SET estado = %s, updated_at = NOW() 
            WHERE id = %s
        """, (nuevo_estado, factura_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?success=pago_agregado", status_code=303)
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=error_interno", status_code=303)

# Eliminar pago
@router.get("/factura/{factura_id}/eliminar-pago/{pago_id}")
def eliminar_pago(factura_id: int, pago_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Eliminar el pago
        cursor.execute("DELETE FROM pagos_factura WHERE id = %s", (pago_id,))
        
        # Recalcular el estado después de eliminar el pago
        cursor.execute("SELECT total, fecha_vencimiento FROM facturas_compra WHERE id = %s", (factura_id,))
        factura = cursor.fetchone()
        
        # Calcular nuevo total pagado
        cursor.execute("SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", (factura_id,))
        resultado = cursor.fetchone()
        total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
        
        # Calcular faltante
        faltante = int(factura["total"]) - total_pagado
        
        # Determinar nuevo estado
        if faltante <= 0:
            nuevo_estado = "pagada"
        else:
            dias_vencido = calcular_dias_vencido(factura["fecha_vencimiento"])
            if dias_vencido > 0:
                nuevo_estado = "vencida"
            else:
                nuevo_estado = "pendiente"
        
        # Actualizar estado
        cursor.execute("""
            UPDATE facturas_compra 
            SET estado = %s, updated_at = NOW() 
            WHERE id = %s
        """, (nuevo_estado, factura_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}", status_code=303)
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=error_eliminacion", status_code=303)

# Función para sincronizar estados de todas las facturas (ejecutar una vez)
@router.get("/sincronizar-estados")
def sincronizar_estados():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener todas las facturas
        cursor.execute("SELECT id, total, fecha_vencimiento FROM facturas_compra")
        facturas = cursor.fetchall()
        
        for factura in facturas:
            # Calcular faltante
            faltante = calcular_faltante_factura(cursor, factura["id"], factura["total"])
            
            # Determinar estado correcto
            if faltante <= 0:
                nuevo_estado = "pagada"
            else:
                dias_vencido = calcular_dias_vencido(factura["fecha_vencimiento"])
                if dias_vencido > 0:
                    nuevo_estado = "vencida"
                else:
                    nuevo_estado = "pendiente"
            
            # Actualizar estado
            cursor.execute("""
                UPDATE facturas_compra 
                SET estado = %s, updated_at = NOW() 
                WHERE id = %s
            """, (nuevo_estado, factura["id"]))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Estados sincronizados correctamente"}
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return {"error": str(e)}