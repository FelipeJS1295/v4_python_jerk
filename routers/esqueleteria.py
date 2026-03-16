from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
from db import conectar_mysql
import mysql.connector
import os

# Cambiamos el prefijo a /produccion y la ruta a /esqueleteria
router = APIRouter(prefix="/produccion", tags=["Esqueletería"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

class ItemOrden(BaseModel):
    modelo_id: int
    cantidad: int

class OrdenEsqueleteriaCreate(BaseModel):
    fecha: str
    ot: str
    esqueletero_id: int
    items: List[ItemOrden]

# ESTA ES LA RUTA QUE DABA 405
@router.get("/esqueleteria", response_class=HTMLResponse)
async def pagina_esqueleteria(request: Request):
    usuario = getattr(request.state, 'usuario', None)
    return templates.TemplateResponse("produccion/esqueleteria.html", {
        "request": request,
        "usuario": usuario
    })

# API Endpoints (Cambiamos las rutas para que sean únicas)
@router.get("/esqueleteria/api/esqueleteros")
def obtener_esqueleteros():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    # Importante: El rol debe coincidir con tu DB 'Esqueletería'
    cursor.execute("SELECT id, nombre_usuario as nombre FROM users WHERE rol = 'Esqueletería' AND activo = 1")
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    return res

@router.get("/esqueleteria/api/modelos")
def obtener_modelos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, costo FROM productos_base")
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    return res

@router.get("/esqueleteria/api/listado")
def listar_ordenes():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT 
            o.id, 
            DATE_FORMAT(o.fecha, '%d-%m-%Y') as fecha, 
            o.ot, 
            u.id as esqueletero_id, -- AGREGAR ESTA LÍNEA
            u.nombre_usuario as esqueletero, 
            o.total_orden,
            GROUP_CONCAT(CONCAT(p.nombre, ' (', d.cantidad, ')') SEPARATOR ', ') as modelos
        FROM esqueleteria_ordenes o
        JOIN users u ON o.esqueletero_id = u.id
        JOIN esqueleteria_detalle d ON o.id = d.orden_id
        JOIN productos_base p ON d.producto_base_id = p.id
        GROUP BY o.id
        ORDER BY o.fecha DESC
    """
    cursor.execute(query)
    res = cursor.fetchall()
    cursor.close()
    conn.close()
    return res

@router.post("/esqueleteria/api/guardar")
def guardar_orden(orden: OrdenEsqueleteriaCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        total_acumulado = 0
        cursor.execute("INSERT INTO esqueleteria_ordenes (fecha, ot, esqueletero_id) VALUES (%s, %s, %s)",
                       (orden.fecha, orden.ot, orden.esqueletero_id))
        orden_id = cursor.lastrowid
        for item in orden.items:
            cursor.execute("SELECT costo FROM productos_base WHERE id = %s", (item.modelo_id,))
            costo = float(cursor.fetchone()[0])
            subtotal = costo * item.cantidad
            total_acumulado += subtotal
            cursor.execute("INSERT INTO esqueleteria_detalle (orden_id, producto_base_id, cantidad, costo_unitario, subtotal) VALUES (%s, %s, %s, %s, %s)",
                           (orden_id, item.modelo_id, item.cantidad, costo, subtotal))
        cursor.execute("UPDATE esqueleteria_ordenes SET total_orden = %s WHERE id = %s", (total_acumulado, orden_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()