from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
from db import conectar_mysql
import mysql.connector
import os

router = APIRouter(prefix="/configuracion/productos", tags=["Productos"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ---------------------------
# MODELOS
# ---------------------------

class InsumoProducto(BaseModel):
    insumo_id: int
    cantidad: float

class ProductoBase(BaseModel):
    sku: str
    nombre: str
    tipo_producto: Optional[str] = None
    tipo_producto_venta: Optional[str] = None
    sku_esqueleto: Optional[str] = None
    sku_hites: Optional[str] = None
    sku_la_polar: Optional[str] = None
    costo_costura: Optional[float] = None
    costo_tapiceria: Optional[float] = None
    costo_armado: Optional[float] = None
    costo_corte: Optional[float] = None
    costo_esqueleteria: Optional[float] = None
    precio_venta: Optional[float] = None
    precio_descuento: Optional[float] = None
    dimensiones: Optional[str] = None
    material: Optional[str] = None
    colores_disponibles: Optional[str] = None
    colores_hex: Optional[str] = None
    tiempo_entrega: Optional[str] = None
    imagen_corte: Optional[str] = None
    imagen_tapizado: Optional[str] = None
    imagen_corte_esqueleto: Optional[str] = None
    imagen_esqueleto: Optional[str] = None
    img_1: Optional[str] = None
    img_2: Optional[str] = None
    img_3: Optional[str] = None
    img_4: Optional[str] = None
    img_5: Optional[str] = None
    img_6: Optional[str] = None
    img_7: Optional[str] = None
    img_8: Optional[str] = None
    img_9: Optional[str] = None
    img_10: Optional[str] = None
    descripcion_producto: Optional[str] = None
    insumos: Optional[List[InsumoProducto]] = []

class ProductoCreate(ProductoBase):
    pass

class ProductoUpdate(ProductoBase):
    id: int

# ---------------------------
# RUTAS
# ---------------------------

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_productos(request: Request):
    return templates.TemplateResponse("configuracion/productos.html", {"request": request})

# RUTA API PARA OBTENER PRODUCTOS
@router.get("/api", response_class=JSONResponse)
def obtener_productos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    return productos

@router.post("/api", response_class=JSONResponse)
def crear_producto(producto: ProductoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO productos (sku, nombre, tipo_producto, tipo_producto_venta, sku_esqueleto, sku_hites, sku_la_polar,
                costo_costura, costo_tapiceria, costo_armado, costo_corte, costo_esqueleteria,
                precio_venta, precio_descuento, dimensiones, material, colores_disponibles,
                colores_hex, tiempo_entrega, imagen_corte, imagen_tapizado, imagen_corte_esqueleto,
                imagen_esqueleto, img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, img_10,
                descripcion_producto)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            producto.sku, producto.nombre, producto.tipo_producto, producto.tipo_producto_venta, producto.sku_esqueleto,
            producto.sku_hites, producto.sku_la_polar, producto.costo_costura, producto.costo_tapiceria,
            producto.costo_armado, producto.costo_corte, producto.costo_esqueleteria, producto.precio_venta,
            producto.precio_descuento, producto.dimensiones, producto.material, producto.colores_disponibles,
            producto.colores_hex, producto.tiempo_entrega, producto.imagen_corte, producto.imagen_tapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.img_1, producto.img_2,
            producto.img_3, producto.img_4, producto.img_5, producto.img_6, producto.img_7, producto.img_8,
            producto.img_9, producto.img_10, producto.descripcion_producto
        ))
        producto_id = cursor.lastrowid

        # Insertar insumos del producto
        for insumo in producto.insumos:
            cursor.execute("""
                INSERT INTO producto_insumo (producto_id, insumo_id, cantidad)
                VALUES (%s, %s, %s)
            """, (producto_id, insumo.insumo_id, insumo.cantidad))

        conn.commit()
        return {"message": "Producto creado correctamente", "producto_id": producto_id}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.put("/api", response_class=JSONResponse)
def actualizar_producto(producto: ProductoUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE productos SET sku=%s, nombre=%s, tipo_producto=%s, tipo_producto_venta=%s,
            sku_esqueleto=%s, sku_hites=%s, sku_la_polar=%s, costo_costura=%s, costo_tapiceria=%s,
            costo_armado=%s, costo_corte=%s, costo_esqueleteria=%s, precio_venta=%s, precio_descuento=%s,
            dimensiones=%s, material=%s, colores_disponibles=%s, colores_hex=%s, tiempo_entrega=%s,
            imagen_corte=%s, imagen_tapizado=%s, imagen_corte_esqueleto=%s, imagen_esqueleto=%s,
            img_1=%s, img_2=%s, img_3=%s, img_4=%s, img_5=%s, img_6=%s, img_7=%s, img_8=%s, img_9=%s, img_10=%s,
            descripcion_producto=%s
            WHERE id=%s
        """, (
            producto.sku, producto.nombre, producto.tipo_producto, producto.tipo_producto_venta, producto.sku_esqueleto,
            producto.sku_hites, producto.sku_la_polar, producto.costo_costura, producto.costo_tapiceria,
            producto.costo_armado, producto.costo_corte, producto.costo_esqueleteria, producto.precio_venta,
            producto.precio_descuento, producto.dimensiones, producto.material, producto.colores_disponibles,
            producto.colores_hex, producto.tiempo_entrega, producto.imagen_corte, producto.imagen_tapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.img_1, producto.img_2,
            producto.img_3, producto.img_4, producto.img_5, producto.img_6, producto.img_7, producto.img_8,
            producto.img_9, producto.img_10, producto.descripcion_producto, producto.id
        ))

        # Eliminar insumos existentes y agregar los nuevos
        cursor.execute("DELETE FROM producto_insumo WHERE producto_id = %s", (producto.id,))

        for insumo in producto.insumos:
            cursor.execute("""
                INSERT INTO producto_insumo (producto_id, insumo_id, cantidad)
                VALUES (%s, %s, %s)
            """, (producto.id, insumo.insumo_id, insumo.cantidad))

        conn.commit()
        return {"message": "Producto actualizado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.delete("/api/{producto_id}", response_class=JSONResponse)
def eliminar_producto(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        # Eliminar relaciones con insumos primero
        cursor.execute("DELETE FROM producto_insumo WHERE producto_id = %s", (producto_id,))
        # Luego eliminar el producto
        cursor.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        return {"message": "Producto eliminado correctamente"}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.get("/api/{producto_id}/insumos", response_class=JSONResponse)
def obtener_insumos_producto(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT pi.insumo_id, pi.cantidad, i.nombre
            FROM producto_insumo pi
            JOIN insumos i ON pi.insumo_id = i.id
            WHERE pi.producto_id = %s
        """, (producto_id,))
        insumos = cursor.fetchall()
        return insumos
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()