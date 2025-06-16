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

# Esquemas
class ProductoBase(BaseModel):
    sku: str
    nombre: str
    sku_esqueleto: Optional[str] = None
    sku_hites: Optional[str] = None
    sku_la_polar: Optional[str] = None
    esqueleto: Optional[str] = None
    imagen_corte: Optional[str] = None
    imagen_tapizado: Optional[str] = None
    imagen_corte_esqueleto: Optional[str] = None
    imagen_esqueleto: Optional[str] = None
    costo_costura: Optional[float] = None
    costo_tapiceria: Optional[float] = None
    costo_armado: Optional[float] = None
    costo_corte: Optional[float] = None
    costo_esqueleteria: Optional[float] = None
    precio_venta: Optional[float] = None
    tipo_producto: Optional[str] = None
    descripcion_producto: Optional[str] = None
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
    precio_descuento: Optional[float] = None
    tipo_producto_venta: Optional[str] = None
    dimensiones: Optional[str] = None
    material: Optional[str] = None
    colores_disponibles: Optional[str] = None
    tiempo_entrega: Optional[str] = None
    colores_hex: Optional[str] = None

class ProductoCreate(ProductoBase):
    insumos: Optional[List[dict]] = []

class ProductoUpdate(ProductoBase):
    id: int
    insumos: Optional[List[dict]] = []

class InsumoProducto(BaseModel):
    insumo_id: int
    cantidad: float

# RUTA PARA SERVIR EL TEMPLATE HTML
@router.get("/", response_class=HTMLResponse)
async def pagina_productos(request: Request):
    return templates.TemplateResponse("configuracion/productos.html", {"request": request})

# RUTAS API
@router.get("/api", response_class=JSONResponse)
def obtener_productos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
               imagen_corte, imagen_tapizado, imagen_corte_esqueleto, imagen_esqueleto,
               costo_costura, costo_tapiceria, costo_armado, costo_corte, costo_esqueleteria,
               precio_venta, tipo_producto, descripcion_producto,
               img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, img_10,
               precio_descuento, tipo_producto_venta, dimensiones, material,
               colores_disponibles, tiempo_entrega, colores_hex, visitas
        FROM productos
        ORDER BY id DESC
    """)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados

@router.get("/api/{producto_id}", response_class=JSONResponse)
def obtener_producto_por_id(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
               imagen_corte, imagen_tapizado, imagen_corte_esqueleto, imagen_esqueleto,
               costo_costura, costo_tapiceria, costo_armado, costo_corte, costo_esqueleteria,
               precio_venta, tipo_producto, descripcion_producto,
               img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, img_10,
               precio_descuento, tipo_producto_venta, dimensiones, material,
               colores_disponibles, tiempo_entrega, colores_hex, visitas
        FROM productos WHERE id = %s
    """, (producto_id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()

    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return producto

@router.post("/api", response_class=JSONResponse)
def crear_producto(producto: ProductoCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        # Insertar producto
        cursor.execute("""
            INSERT INTO productos (
                sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
                imagen_corte, imagen_tapizado, imagen_corte_esqueleto, imagen_esqueleto,
                costo_costura, costo_tapiceria, costo_armado, costo_corte, costo_esqueleteria,
                precio_venta, tipo_producto, descripcion_producto,
                img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, img_10,
                precio_descuento, tipo_producto_venta, dimensiones, material,
                colores_disponibles, tiempo_entrega, colores_hex
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_la_polar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_tapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_tapiceria, producto.costo_armado, producto.costo_corte,
            producto.costo_esqueleteria, producto.precio_venta, producto.tipo_producto,
            producto.descripcion_producto, producto.img_1, producto.img_2, producto.img_3,
            producto.img_4, producto.img_5, producto.img_6, producto.img_7, producto.img_8,
            producto.img_9, producto.img_10, producto.precio_descuento, producto.tipo_producto_venta,
            producto.dimensiones, producto.material, producto.colores_disponibles,
            producto.tiempo_entrega, producto.colores_hex
        ))
        
        producto_id = cursor.lastrowid
        
        # Insertar insumos si los hay
        if producto.insumos:
            for insumo in producto.insumos:
                cursor.execute("""
                    INSERT INTO producto_insumo (producto_id, insumo_id, cantidad)
                    VALUES (%s, %s, %s)
                """, (producto_id, insumo['insumo_id'], insumo['cantidad']))
        
        conn.commit()
        return {"message": "Producto creado correctamente", "id": producto_id}
        
    except mysql.connector.Error as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.put("/api", response_class=JSONResponse)
def actualizar_producto(producto: ProductoUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        # Actualizar producto
        cursor.execute("""
            UPDATE productos SET
                sku=%s, sku_esqueleto=%s, sku_hites=%s, sku_la_polar=%s, nombre=%s, esqueleto=%s,
                imagen_corte=%s, imagen_tapizado=%s, imagen_corte_esqueleto=%s, imagen_esqueleto=%s,
                costo_costura=%s, costo_tapiceria=%s, costo_armado=%s, costo_corte=%s, costo_esqueleteria=%s,
                precio_venta=%s, tipo_producto=%s, descripcion_producto=%s,
                img_1=%s, img_2=%s, img_3=%s, img_4=%s, img_5=%s, img_6=%s, img_7=%s, img_8=%s, img_9=%s, img_10=%s,
                precio_descuento=%s, tipo_producto_venta=%s, dimensiones=%s, material=%s,
                colores_disponibles=%s, tiempo_entrega=%s, colores_hex=%s
            WHERE id=%s
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_la_polar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_tapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_tapiceria, producto.costo_armado, producto.costo_corte,
            producto.costo_esqueleteria, producto.precio_venta, producto.tipo_producto,
            producto.descripcion_producto, producto.img_1, producto.img_2, producto.img_3,
            producto.img_4, producto.img_5, producto.img_6, producto.img_7, producto.img_8,
            producto.img_9, producto.img_10, producto.precio_descuento, producto.tipo_producto_venta,
            producto.dimensiones, producto.material, producto.colores_disponibles,
            producto.tiempo_entrega, producto.colores_hex, producto.id
        ))
        
        # Actualizar insumos - eliminar existentes y crear nuevos
        cursor.execute("DELETE FROM producto_insumo WHERE producto_id = %s", (producto.id,))
        
        if producto.insumos:
            for insumo in producto.insumos:
                cursor.execute("""
                    INSERT INTO producto_insumo (producto_id, insumo_id, cantidad)
                    VALUES (%s, %s, %s)
                """, (producto.id, insumo['insumo_id'], insumo['cantidad']))
        
        conn.commit()
        return {"message": "Producto actualizado correctamente"}
        
    except mysql.connector.Error as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.delete("/api/{producto_id}", response_class=JSONResponse)
def eliminar_producto(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        # Primero eliminar insumos relacionados
        cursor.execute("DELETE FROM producto_insumo WHERE producto_id = %s", (producto_id,))
        
        # Luego eliminar el producto
        cursor.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        
        return {"message": "Producto eliminado correctamente"}
        
    except mysql.connector.Error as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.get("/api/{producto_id}/insumos", response_class=JSONResponse)
def obtener_insumos_producto(producto_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT pi.insumo_id, pi.cantidad, i.nombre as insumo_nombre, i.sku_padre
        FROM producto_insumo pi
        JOIN insumos i ON pi.insumo_id = i.id
        WHERE pi.producto_id = %s
    """, (producto_id,))
    insumos = cursor.fetchall()
    cursor.close()
    conn.close()
    return insumos