from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
import mysql.connector
import os

router = APIRouter(prefix="/configuracion/proveedores", tags=["Proveedores"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Esquemas
class ProveedorBase(BaseModel):
    rut: str
    nombre: str
    direccion: Optional[str] = None
    contacto: Optional[str] = None
    forma_pago: Optional[str] = None

class ProveedorCreate(ProveedorBase):
    pass

class ProveedorUpdate(ProveedorBase):
    id: int

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_proveedores(request: Request):
    return templates.TemplateResponse("configuracion/proveedores.html", {"request": request})

# RUTAS API
@router.get("/api", response_class=JSONResponse)
def obtener_proveedores():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, rut, nombre, direccion, contacto, forma_pago FROM proveedores")
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

@router.get("/api/{proveedor_id}", response_class=JSONResponse)
def obtener_proveedor_por_id(proveedor_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, rut, nombre, direccion, contacto, forma_pago FROM proveedores WHERE id = %s", (proveedor_id,))
    proveedor = cursor.fetchone()
    cursor.close()
    conn.close()

    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    return proveedor

@router.post("/api", response_class=JSONResponse)
def crear_proveedor(proveedor: ProveedorCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO proveedores (rut, nombre, direccion, contacto, forma_pago)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            proveedor.rut,
            proveedor.nombre,
            proveedor.direccion,
            proveedor.contacto,
            proveedor.forma_pago
        ))
        conn.commit()
        return {"message": "Proveedor creado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.put("/api", response_class=JSONResponse)
def actualizar_proveedor(proveedor: ProveedorUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE proveedores SET rut=%s, nombre=%s, direccion=%s, contacto=%s, forma_pago=%s WHERE id=%s
        """, (
            proveedor.rut,
            proveedor.nombre,
            proveedor.direccion,
            proveedor.contacto,
            proveedor.forma_pago,
            proveedor.id
        ))
        conn.commit()
        return {"message": "Proveedor actualizado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.delete("/api/{proveedor_id}", response_class=JSONResponse)
def eliminar_proveedor(proveedor_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM proveedores WHERE id = %s", (proveedor_id,))
        conn.commit()
        return {"message": "Proveedor eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()