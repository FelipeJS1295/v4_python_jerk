from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import mysql.connector
from db import conectar_mysql
import os

router = APIRouter(prefix="/configuracion/clientes", tags=["Clientes"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Esquema para Cliente
class ClienteBase(BaseModel):
    rut: str
    nombre: str
    direccion: Optional[str] = None
    contacto: Optional[str] = None
    dias_pago: Optional[int] = None
    porcentaje_comision: Optional[float] = None
    cobro_logistico: Optional[float] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(ClienteBase):
    id: int

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_clientes(request: Request):
    return templates.TemplateResponse("configuracion/clientes.html", {"request": request})

# RUTA API PARA OBTENER DATOS JSON
@router.get("/api", response_class=JSONResponse)
def listar_clientes():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes")
    clientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return clientes

# Crear cliente
@router.post("/api", response_class=JSONResponse)
def crear_cliente(cliente: ClienteCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO clientes (rut, nombre, direccion, contacto, dias_pago, porcentaje_comision, cobro_logistico)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            cliente.rut,
            cliente.nombre,
            cliente.direccion,
            cliente.contacto,
            cliente.dias_pago,
            cliente.porcentaje_comision,
            cliente.cobro_logistico
        ))
        conn.commit()
        return {"message": "Cliente creado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# Actualizar cliente
@router.put("/api", response_class=JSONResponse)
def actualizar_cliente(cliente: ClienteUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE clientes SET rut=%s, nombre=%s, direccion=%s, contacto=%s, dias_pago=%s,
            porcentaje_comision=%s, cobro_logistico=%s WHERE id=%s
        """, (
            cliente.rut,
            cliente.nombre,
            cliente.direccion,
            cliente.contacto,
            cliente.dias_pago,
            cliente.porcentaje_comision,
            cliente.cobro_logistico,
            cliente.id
        ))
        conn.commit()
        return {"message": "Cliente actualizado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# Eliminar cliente
@router.delete("/api/{cliente_id}", response_class=JSONResponse)
def eliminar_cliente(cliente_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
        conn.commit()
        return {"message": "Cliente eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()