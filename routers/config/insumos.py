from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
import mysql.connector
import os

router = APIRouter(prefix="/configuracion/insumos", tags=["Insumos"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# -------------------------
# Esquemas
# -------------------------
class InsumoBase(BaseModel):
    sku_padre: str
    sku_hijo: Optional[str] = None
    nombre: str
    unidad_medida: str
    proveedor_id: int
    precio_costo: float
    precio_venta: float

class InsumoCreate(InsumoBase):
    pass

class InsumoUpdate(InsumoBase):
    id: int

# -------------------------
# Rutas
# -------------------------

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_insumos(request: Request):
    return templates.TemplateResponse("configuracion/insumos.html", {"request": request})

# RUTA API PARA OBTENER DATOS JSON
@router.get("/api", response_class=JSONResponse)
def obtener_insumos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM insumos")
    insumos = cursor.fetchall()
    cursor.close()
    conn.close()
    return insumos

@router.post("/api", response_class=JSONResponse)
def crear_insumo(insumo: InsumoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO insumos 
            (sku_padre, sku_hijo, nombre, unidad_medida, proveedor_id, precio_costo, precio_venta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            insumo.sku_padre,
            insumo.sku_hijo,
            insumo.nombre,
            insumo.unidad_medida,
            insumo.proveedor_id,
            insumo.precio_costo,
            insumo.precio_venta
        ))
        conn.commit()
        return {"message": "Insumo creado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.put("/api", response_class=JSONResponse)
def actualizar_insumo(insumo: InsumoUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE insumos SET sku_padre=%s, sku_hijo=%s, nombre=%s, unidad_medida=%s, 
            proveedor_id=%s, precio_costo=%s, precio_venta=%s WHERE id=%s
        """, (
            insumo.sku_padre,
            insumo.sku_hijo,
            insumo.nombre,
            insumo.unidad_medida,
            insumo.proveedor_id,
            insumo.precio_costo,
            insumo.precio_venta,
            insumo.id
        ))
        conn.commit()
        return {"message": "Insumo actualizado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.delete("/api/{insumo_id}", response_class=JSONResponse)
def eliminar_insumo(insumo_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM insumos WHERE id = %s", (insumo_id,))
        conn.commit()
        return {"message": "Insumo eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()