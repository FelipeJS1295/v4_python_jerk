from fastapi import APIRouter, HTTPException
from db import conectar_mysql
from schemas.producto_insumo_schema import ProductoInsumoCreate, ProductoInsumoOut

router = APIRouter(prefix="/producto-insumo", tags=["ProductoInsumo"])

@router.post("/", response_model=dict)
def asignar_insumos_a_producto(data: ProductoInsumoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        for item in data.insumos:
            cursor.execute(
                """
                INSERT INTO producto_insumo (producto_id, insumo_id, cantidad)
                VALUES (%s, %s, %s)
                """,
                (data.producto_id, item.insumo_id, item.cantidad)
            )
        conn.commit()
        conn.close()
        return {"mensaje": "Insumos asignados correctamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{producto_id}", response_model=list[ProductoInsumoOut])
def obtener_insumos_de_producto(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, producto_id, insumo_id, cantidad
        FROM producto_insumo
        WHERE producto_id = %s
    """, (producto_id,))
    resultados = cursor.fetchall()
    conn.close()
    return resultados
