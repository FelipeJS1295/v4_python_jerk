from fastapi import APIRouter, HTTPException
from db import conectar_mysql
from schemas.insumo_schema import InsumoCreate, InsumoOut

router = APIRouter(prefix="/insumos", tags=["Insumos"])

@router.get("/", response_model=list[InsumoOut])
def obtener_insumos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, sku_padre, sku_hijo, nombre, unidad_medida, proveedor_id,
               precio_costo, precio_venta
        FROM insumos
    """)
    resultados = cursor.fetchall()
    conn.close()
    return resultados

@router.post("/", response_model=InsumoOut)
def crear_insumo(insumo: InsumoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO insumos (sku_padre, sku_hijo, nombre, unidad_medida, proveedor_id,
                                 precio_costo, precio_venta)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                insumo.sku_padre,
                insumo.sku_hijo,
                insumo.nombre,
                insumo.unidad_medida,
                insumo.proveedor_id,
                insumo.precio_costo,
                insumo.precio_venta
            )
        )
        conn.commit()
        insumo_id = cursor.lastrowid
        conn.close()
        return {"id": insumo_id, **insumo.dict()}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
