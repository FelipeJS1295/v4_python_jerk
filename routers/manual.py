from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime
from db import conectar_mysql

router = APIRouter()

# Modelo para cada producto incluido en la venta
class ProductoVenta(BaseModel):
    producto: str
    cantidad: int
    fecha_entrega: str  # Formato YYYY-MM-DD

# Modelo principal de venta manual
class VentaManual(BaseModel):
    cliente_id: int
    numero_orden: str
    fecha_compra: str
    productos: List[ProductoVenta]

@router.post("/ventas/manual/preview", response_class=JSONResponse)
async def preview_venta_manual(venta: VentaManual):
    """Previsualiza la venta con los productos antes de guardar"""
    return {"preview": venta, "total_productos": len(venta.productos)}

@router.post("/ventas/manual/guardar", response_class=JSONResponse)
async def guardar_venta_manual(venta: VentaManual):
    conn = None
    cursor = None
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        insertadas = 0

        for item in venta.productos:
            # Obtener el SKU usando el nombre del producto
            cursor.execute("SELECT sku FROM productos WHERE nombre = %s LIMIT 1", (item.producto,))
            resultado = cursor.fetchone()
            sku = resultado["sku"] if resultado else None  # puede ser None si no lo encuentra

            for i in range(item.cantidad):
                cursor.execute("""
                    INSERT INTO ventas_retail (
                        cliente_id, numero_orden, fecha_compra, producto, sku, fecha_entrega,
                        estado, unidades, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                """, (
                    venta.cliente_id,
                    venta.numero_orden,
                    venta.fecha_compra,
                    item.producto,   # Se guarda el nombre
                    sku,             # Se guarda el SKU asociado
                    item.fecha_entrega,
                    "nueva",
                    1
                ))

                insertadas += 1

        conn.commit()
        return {"mensaje": f"Se registraron {insertadas} unidades para la orden {venta.numero_orden}"}

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar la venta: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

