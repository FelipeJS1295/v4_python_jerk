from fastapi import APIRouter, HTTPException
from db import conectar_mysql
from schemas.producto_schema import ProductoCreate, ProductoOut

router = APIRouter(prefix="/productos", tags=["Productos"])

@router.get("/", response_model=list[ProductoOut])
def obtener_productos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM productos
    """)
    resultados = cursor.fetchall()
    conn.close()
    return resultados

@router.post("/", response_model=ProductoOut)
def crear_producto(producto: ProductoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        columnas = [
            "sku", "sku_esqueleto", "sku_hites", "sku_la_polar", "nombre",
            "esqueleto", "imagen_corte", "imagen_tapizado", "imagen_corte_esqueleto",
            "imagen_esqueleto", "costo_costura", "costo_tapiceria", "costo_armado",
            "costo_corte", "costo_esqueleteria", "users_id", "precio_venta",
            "tipo_producto", "descripcion_producto", "producto_imagenes_venta_id",
            "img_1", "img_2", "img_3", "img_4", "img_5", "img_6", "img_7", "img_8",
            "img_9", "img_10", "precio_descuento", "tipo_producto_venta", "visitas",
            "dimensiones", "material", "colores_disponibles", "tiempo_entrega",
            "colores_hex"
        ]
        valores = [getattr(producto, col) for col in columnas]

        placeholders = ", ".join(["%s"] * len(columnas))
        columnas_str = ", ".join(columnas)

        cursor.execute(
            f"""
            INSERT INTO productos ({columnas_str})
            VALUES ({placeholders})
            """,
            valores
        )
        conn.commit()
        producto_id = cursor.lastrowid
        conn.close()
        return {"id": producto_id, **producto.dict()}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
