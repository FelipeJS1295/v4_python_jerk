from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
import mysql.connector

router = APIRouter(prefix="/configuracion/proveedores", tags=["Proveedores"])

# ------------------------
# Modelos
# ------------------------

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

# ------------------------
# Endpoints
# ------------------------

@router.get("/", response_class=JSONResponse)
def obtener_proveedores():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM proveedores")
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados


@router.post("/", response_class=JSONResponse)
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
        raise HTTPException(status_code=500, detail=f"Error al crear proveedor: {err}")
    finally:
        cursor.close()
        conn.close()


@router.put("/", response_class=JSONResponse)
def actualizar_proveedor(proveedor: ProveedorUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE proveedores
            SET rut=%s, nombre=%s, direccion=%s, contacto=%s, forma_pago=%s
            WHERE id=%s
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
        raise HTTPException(status_code=500, detail=f"Error al actualizar proveedor: {err}")
    finally:
        cursor.close()
        conn.close()


@router.delete("/{proveedor_id}", response_class=JSONResponse)
def eliminar_proveedor(proveedor_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM proveedores WHERE id = %s", (proveedor_id,))
        conn.commit()
        return {"message": "Proveedor eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error al eliminar proveedor: {err}")
    finally:
        cursor.close()
        conn.close()
