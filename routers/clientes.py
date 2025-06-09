from fastapi import APIRouter, HTTPException
from db import conectar_mysql
from schemas.cliente_schema import ClienteCreate, ClienteOut

router = APIRouter(prefix="/clientes", tags=["Clientes"])

@router.get("/", response_model=list[ClienteOut])
def obtener_clientes():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, nombre, rut, direccion, contacto, dias_pago, porcentaje_comision, cobro_logistico
        FROM clientes
    """)
    resultados = cursor.fetchall()
    conn.close()
    return resultados

@router.post("/", response_model=ClienteOut)
def crear_cliente(cliente: ClienteCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO clientes (nombre, rut, direccion, contacto, dias_pago, porcentaje_comision, cobro_logistico)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                cliente.nombre,
                cliente.rut,
                cliente.direccion,
                cliente.contacto,
                cliente.dias_pago,
                cliente.porcentaje_comision,
                cliente.cobro_logistico
            )
        )
        conn.commit()
        cliente_id = cursor.lastrowid
        conn.close()
        return {"id": cliente_id, **cliente.dict()}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))