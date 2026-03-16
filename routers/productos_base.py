from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
import mysql.connector
import os

# Prefijo actualizado para Productos Base
router = APIRouter(prefix="/configuracion/productos-base", tags=["Productos Base"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Esquemas
class ProductoBaseSchema(BaseModel):
    codigo: str
    nombre: str
    categoria: Optional[str] = None
    costo: float = 0.0 # Columna costo agregada

class ProductoBaseCreate(ProductoBaseSchema):
    pass

class ProductoBaseUpdate(ProductoBaseSchema):
    id: int

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_productos_base(request: Request):
    return templates.TemplateResponse("configuracion/productos_base.html", {"request": request})

# RUTAS API
@router.get("/api", response_class=JSONResponse)
def obtener_productos_base():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    # Seleccionamos el costo también
    cursor.execute("SELECT id, codigo, nombre, categoria, costo FROM productos_base")
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

@router.get("/api/{producto_id}", response_class=JSONResponse)
def obtener_producto_base_por_id(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, codigo, nombre, categoria, costo FROM productos_base WHERE id = %s", (producto_id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    if not producto:
        raise HTTPException(status_code=404, detail="Producto base no encontrado")

    return producto

@router.post("/api", response_class=JSONResponse)
def crear_producto_base(producto: ProductoBaseCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO productos_base (codigo, nombre, categoria, costo)
            VALUES (%s, %s, %s, %s)
        """, (
            producto.codigo,
            producto.nombre,
            producto.categoria,
            producto.costo
        ))
        conn.commit()
        return {"message": "Producto base creado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.put("/api", response_class=JSONResponse)
def actualizar_producto_base(producto: ProductoBaseUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE productos_base SET codigo=%s, nombre=%s, categoria=%s, costo=%s WHERE id=%s
        """, (
            producto.codigo,
            producto.nombre,
            producto.categoria,
            producto.costo,
            producto.id
        ))
        conn.commit()
        return {"message": "Producto base actualizado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.delete("/api/{producto_id}", response_class=JSONResponse)
def eliminar_producto_base(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM productos_base WHERE id = %s", (producto_id,))
        conn.commit()
        return {"message": "Producto base eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# RUTA PARA EL TOTAL (Usada por el Dashboard)
@router.get("/total")
def obtener_total_productos_base():
    conn = conectar_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM productos_base")
    total = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return {"total": total}