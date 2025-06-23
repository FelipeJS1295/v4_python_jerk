from fastapi import APIRouter, Request, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql
from pydantic import BaseModel
from typing import Optional, List
import os
import shutil
from pathlib import Path
import mysql.connector
from datetime import datetime

router = APIRouter(prefix="/configuracion/productos", tags=["Productos"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Rutas de imágenes
PRODUCTOS_IMG_PATH = "/var/www/imagenes_jhk/productos"
SHOW_IMG_PATH = "/var/www/imagenes_jhk/show"

# Crear directorios si no existen
os.makedirs(PRODUCTOS_IMG_PATH, exist_ok=True)
os.makedirs(SHOW_IMG_PATH, exist_ok=True)

# Esquemas Pydantic
class ProductoBase(BaseModel):
    sku: Optional[str] = None
    sku_esqueleto: Optional[str] = None
    sku_hites: Optional[str] = None
    sku_lapolar: Optional[str] = None
    nombre: str
    esqueleto: Optional[str] = None
    imagen_corte: Optional[str] = None
    imagen_lapizado: Optional[str] = None
    imagen_corte_esqueleto: Optional[str] = None
    imagen_esqueleto: Optional[str] = None
    costo_costura: Optional[float] = 0.0
    costo_lapiceria: Optional[float] = 0.0
    costo_esqueleteria: Optional[float] = 0.0
    costo_armado: Optional[float] = 0.0
    costo_corte: Optional[float] = 0.0
    precio_venta: Optional[float] = 0.0
    tipo_producto: Optional[str] = None
    descripcion_producto: Optional[str] = None
    material: Optional[str] = None
    colores_disponibles: Optional[str] = None
    tiempo_entrega: Optional[str] = None
    dimensiones: Optional[str] = None
    precio_descuento: Optional[float] = 0.0
    visitas: Optional[int] = 0

class ProductoCreate(ProductoBase):
    pass

class ProductoUpdate(ProductoBase):
    id: int

# RUTAS HTML - VISTAS
@router.get("/", response_class=HTMLResponse)
async def productos_index(request: Request):
    """Página principal de productos"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                id, sku, nombre, tipo_producto, precio_venta, 
                costo_armado, img_1, visitas, created_at
            FROM productos 
            ORDER BY created_at DESC
        """)
        productos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return templates.TemplateResponse("configuracion/productos/index.html", {
            "request": request,
            "productos": productos
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener productos: {str(e)}")

@router.get("/create", response_class=HTMLResponse)
async def productos_create_form(request: Request):
    """Formulario para crear producto"""
    return templates.TemplateResponse("configuracion/productos/create.html", {
        "request": request
    })

@router.get("/edit/{producto_id}", response_class=HTMLResponse)
async def productos_edit_form(request: Request, producto_id: int):
    """Formulario para editar producto"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        return templates.TemplateResponse("configuracion/productos/edit.html", {
            "request": request,
            "producto": producto
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener producto: {str(e)}")

@router.get("/show/{producto_id}", response_class=HTMLResponse)
async def productos_show(request: Request, producto_id: int):
    """Vista detallada del producto"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        return templates.TemplateResponse("configuracion/productos/show.html", {
            "request": request,
            "producto": producto
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener producto: {str(e)}")

# RUTAS API - CRUD
@router.get("/api", response_class=JSONResponse)
def obtener_productos_api():
    """API para obtener todos los productos"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                id, sku, sku_esqueleto, sku_hites, sku_lapolar, nombre, 
                esqueleto, imagen_corte, imagen_lapizado, imagen_corte_esqueleto, 
                imagen_esqueleto, costo_costura, costo_lapiceria, costo_esqueleteria, 
                costo_armado, costo_corte, precio_venta, tipo_producto, 
                descripcion_producto, material, colores_disponibles, tiempo_entrega, 
                dimensiones, precio_descuento, visitas, created_at, updated_at,
                img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, img_10
            FROM productos 
            ORDER BY created_at DESC
        """)
        productos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return productos
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener productos: {str(e)}")

@router.get("/api/{producto_id}", response_class=JSONResponse)
def obtener_producto_por_id_api(producto_id: int):
    """API para obtener un producto específico"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        return producto
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener producto: {str(e)}")

@router.post("/api", response_class=JSONResponse)
def crear_producto_api(producto: ProductoCreate):
    """API para crear un nuevo producto"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO productos (
                sku, sku_esqueleto, sku_hites, sku_lapolar, nombre, esqueleto,
                imagen_corte, imagen_lapizado, imagen_corte_esqueleto, imagen_esqueleto,
                costo_costura, costo_lapiceria, costo_esqueleteria, costo_armado, costo_corte,
                precio_venta, tipo_producto, descripcion_producto, material, colores_disponibles,
                tiempo_entrega, dimensiones, precio_descuento, visitas, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_lapolar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_lapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_lapiceria, producto.costo_esqueleteria, producto.costo_armado,
            producto.costo_corte, producto.precio_venta, producto.tipo_producto,
            producto.descripcion_producto, producto.material, producto.colores_disponibles,
            producto.tiempo_entrega, producto.dimensiones, producto.precio_descuento,
            producto.visitas, datetime.now()
        ))
        
        producto_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Producto creado correctamente", "id": producto_id}
        
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(err)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear producto: {str(e)}")

@router.put("/api/{producto_id}", response_class=JSONResponse)
def actualizar_producto_api(producto_id: int, producto: ProductoUpdate):
    """API para actualizar un producto"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE productos SET
                sku = %s, sku_esqueleto = %s, sku_hites = %s, sku_lapolar = %s,
                nombre = %s, esqueleto = %s, imagen_corte = %s, imagen_lapizado = %s,
                imagen_corte_esqueleto = %s, imagen_esqueleto = %s, costo_costura = %s,
                costo_lapiceria = %s, costo_esqueleteria = %s, costo_armado = %s,
                costo_corte = %s, precio_venta = %s, tipo_producto = %s,
                descripcion_producto = %s, material = %s, colores_disponibles = %s,
                tiempo_entrega = %s, dimensiones = %s, precio_descuento = %s,
                visitas = %s, updated_at = %s
            WHERE id = %s
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_lapolar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_lapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_lapiceria, producto.costo_esqueleteria, producto.costo_armado,
            producto.costo_corte, producto.precio_venta, producto.tipo_producto,
            producto.descripcion_producto, producto.material, producto.colores_disponibles,
            producto.tiempo_entrega, producto.dimensiones, producto.precio_descuento,
            producto.visitas, datetime.now(), producto_id
        ))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Producto actualizado correctamente"}
        
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(err)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")

@router.delete("/api/{producto_id}", response_class=JSONResponse)
def eliminar_producto_api(producto_id: int):
    """API para eliminar un producto"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        # Primero obtener el producto para eliminar imágenes
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cursor.fetchone()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Eliminar producto de la base de datos
        cursor.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Producto eliminado correctamente"}
        
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(err)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar producto: {str(e)}")

# RUTAS PARA MANEJO DE IMÁGENES
@router.post("/upload-images/{producto_id}")
async def subir_imagenes_producto(
    producto_id: int,
    img_1: Optional[UploadFile] = File(None),
    img_2: Optional[UploadFile] = File(None),
    img_3: Optional[UploadFile] = File(None),
    img_4: Optional[UploadFile] = File(None),
    img_5: Optional[UploadFile] = File(None),
    img_6: Optional[UploadFile] = File(None),
    img_7: Optional[UploadFile] = File(None),
    img_8: Optional[UploadFile] = File(None),
    img_9: Optional[UploadFile] = File(None),
    img_10: Optional[UploadFile] = File(None)
):
    """Subir imágenes de productos (img_1 a img_10)"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        imagenes = {
            'img_1': img_1, 'img_2': img_2, 'img_3': img_3, 'img_4': img_4, 'img_5': img_5,
            'img_6': img_6, 'img_7': img_7, 'img_8': img_8, 'img_9': img_9, 'img_10': img_10
        }
        
        rutas_guardadas = {}
        
        for campo, archivo in imagenes.items():
            if archivo and archivo.filename:
                # Generar nombre único
                extension = archivo.filename.split('.')[-1]
                nombre_archivo = f"{producto_id}_{campo}.{extension}"
                ruta_archivo = os.path.join(PRODUCTOS_IMG_PATH, nombre_archivo)
                
                # Guardar archivo
                with open(ruta_archivo, "wb") as buffer:
                    shutil.copyfileobj(archivo.file, buffer)
                
                rutas_guardadas[campo] = nombre_archivo
        
        # Actualizar base de datos
        if rutas_guardadas:
            set_clause = ", ".join([f"{campo} = %s" for campo in rutas_guardadas.keys()])
            valores = list(rutas_guardadas.values()) + [producto_id]
            
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE id = %s", valores)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Imágenes subidas correctamente", "rutas": rutas_guardadas}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imágenes: {str(e)}")

@router.post("/upload-show-images/{producto_id}")
async def subir_imagenes_show(
    producto_id: int,
    imagen_corte: Optional[UploadFile] = File(None),
    imagen_lapizado: Optional[UploadFile] = File(None),
    imagen_corte_esqueleto: Optional[UploadFile] = File(None),
    imagen_esqueleto: Optional[UploadFile] = File(None)
):
    """Subir imágenes de show (esqueletería, corte, etc.)"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        imagenes = {
            'imagen_corte': imagen_corte,
            'imagen_lapizado': imagen_lapizado,
            'imagen_corte_esqueleto': imagen_corte_esqueleto,
            'imagen_esqueleto': imagen_esqueleto
        }
        
        rutas_guardadas = {}
        
        for campo, archivo in imagenes.items():
            if archivo and archivo.filename:
                # Generar nombre único
                extension = archivo.filename.split('.')[-1]
                nombre_archivo = f"{producto_id}_{campo}.{extension}"
                ruta_archivo = os.path.join(SHOW_IMG_PATH, nombre_archivo)
                
                # Guardar archivo
                with open(ruta_archivo, "wb") as buffer:
                    shutil.copyfileobj(archivo.file, buffer)
                
                rutas_guardadas[campo] = nombre_archivo
        
        # Actualizar base de datos
        if rutas_guardadas:
            set_clause = ", ".join([f"{campo} = %s" for campo in rutas_guardadas.keys()])
            valores = list(rutas_guardadas.values()) + [producto_id]
            
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE id = %s", valores)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Imágenes de show subidas correctamente", "rutas": rutas_guardadas}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imágenes de show: {str(e)}")

# RUTAS PARA FORMULARIOS HTML
@router.post("/create")
async def crear_producto_form(
    request: Request,
    sku: str = Form(...),
    nombre: str = Form(...),
    tipo_producto: str = Form(""),
    precio_venta: float = Form(0.0),
    descripcion_producto: str = Form(""),
    material: str = Form(""),
    colores_disponibles: str = Form(""),
    tiempo_entrega: str = Form(""),
    dimensiones: str = Form(""),
    costo_costura: float = Form(0.0),
    costo_lapiceria: float = Form(0.0),
    costo_esqueleteria: float = Form(0.0),
    costo_armado: float = Form(0.0),
    costo_corte: float = Form(0.0)
):
    """Crear producto desde formulario HTML"""
    try:
        producto = ProductoCreate(
            sku=sku,
            nombre=nombre,
            tipo_producto=tipo_producto,
            precio_venta=precio_venta,
            descripcion_producto=descripcion_producto,
            material=material,
            colores_disponibles=colores_disponibles,
            tiempo_entrega=tiempo_entrega,
            dimensiones=dimensiones,
            costo_costura=costo_costura,
            costo_lapiceria=costo_lapiceria,
            costo_esqueleteria=costo_esqueleteria,
            costo_armado=costo_armado,
            costo_corte=costo_corte
        )
        
        resultado = crear_producto_api(producto)
        return RedirectResponse(url="/configuracion/productos/", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear producto: {str(e)}")

@router.post("/edit/{producto_id}")
async def actualizar_producto_form(
    request: Request,
    producto_id: int,
    sku: str = Form(...),
    nombre: str = Form(...),
    tipo_producto: str = Form(""),
    precio_venta: float = Form(0.0),
    descripcion_producto: str = Form(""),
    material: str = Form(""),
    colores_disponibles: str = Form(""),
    tiempo_entrega: str = Form(""),
    dimensiones: str = Form(""),
    costo_costura: float = Form(0.0),
    costo_lapiceria: float = Form(0.0),
    costo_esqueleteria: float = Form(0.0),
    costo_armado: float = Form(0.0),
    costo_corte: float = Form(0.0)
):
    """Actualizar producto desde formulario HTML"""
    try:
        producto = ProductoUpdate(
            id=producto_id,
            sku=sku,
            nombre=nombre,
            tipo_producto=tipo_producto,
            precio_venta=precio_venta,
            descripcion_producto=descripcion_producto,
            material=material,
            colores_disponibles=colores_disponibles,
            tiempo_entrega=tiempo_entrega,
            dimensiones=dimensiones,
            costo_costura=costo_costura,
            costo_lapiceria=costo_lapiceria,
            costo_esqueleteria=costo_esqueleteria,
            costo_armado=costo_armado,
            costo_corte=costo_corte
        )
        
        actualizar_producto_api(producto_id, producto)
        return RedirectResponse(url="/configuracion/productos/", status_code=303)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")