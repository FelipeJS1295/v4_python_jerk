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
templates = Jinja2Templates(directory="templates")

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
    sku_la_polar: Optional[str] = None
    nombre: str
    esqueleto: Optional[str] = None
    imagen_corte: Optional[str] = None
    imagen_lapizado: Optional[str] = None
    imagen_corte_esqueleto: Optional[str] = None
    imagen_esqueleto: Optional[str] = None
    costo_costura: Optional[float] = 0.0
    costo_tapiceria: Optional[float] = 0.0
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
        if not conn:
            raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
            
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
            "productos": productos or []
        })
        
    except Exception as e:
        print(f"Error en productos_index: {str(e)}")  # Para debug
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
                id, sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, 
                esqueleto, imagen_corte, imagen_lapizado, imagen_corte_esqueleto, 
                imagen_esqueleto, costo_costura, costo_tapiceria, costo_esqueleteria, 
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
                sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
                imagen_corte, imagen_lapizado, imagen_corte_esqueleto, imagen_esqueleto,
                costo_costura, costo_tapiceria, costo_esqueleteria, costo_armado, costo_corte,
                precio_venta, tipo_producto, descripcion_producto, material, colores_disponibles,
                tiempo_entrega, dimensiones, precio_descuento, visitas, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_la_polar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_lapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_tapiceria, producto.costo_esqueleteria, producto.costo_armado,
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
                sku = %s, sku_esqueleto = %s, sku_hites = %s, sku_la_polar = %s,
                nombre = %s, esqueleto = %s, imagen_corte = %s, imagen_lapizado = %s,
                imagen_corte_esqueleto = %s, imagen_esqueleto = %s, costo_costura = %s,
                costo_tapiceria = %s, costo_esqueleteria = %s, costo_armado = %s,
                costo_corte = %s, precio_venta = %s, tipo_producto = %s,
                descripcion_producto = %s, material = %s, colores_disponibles = %s,
                tiempo_entrega = %s, dimensiones = %s, precio_descuento = %s,
                visitas = %s, updated_at = %s
            WHERE id = %s
        """, (
            producto.sku, producto.sku_esqueleto, producto.sku_hites, producto.sku_la_polar,
            producto.nombre, producto.esqueleto, producto.imagen_corte, producto.imagen_lapizado,
            producto.imagen_corte_esqueleto, producto.imagen_esqueleto, producto.costo_costura,
            producto.costo_tapiceria, producto.costo_esqueleteria, producto.costo_armado,
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
                
                rutas_guardadas[campo] = f"/imagenes/productos/{nombre_archivo}"
        
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
                
                rutas_guardadas[campo] = f"/imagenes/show/{nombre_archivo}"
        
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
    sku_esqueleto: str = Form(""),
    sku_hites: str = Form(""),
    sku_la_polar: str = Form(""),
    esqueleto: str = Form(""),
    tipo_producto: str = Form(""),
    descripcion_producto: str = Form(""),
    material: str = Form(""),
    colores_disponibles: str = Form(""),
    tiempo_entrega: str = Form(""),
    dimensiones: str = Form(""),
    colores_hex: str = Form(""),
    tipo_producto_venta: str = Form(""),
    producto_imagenes_venta_id: Optional[str] = Form(""),
    precio_venta: Optional[float] = Form(None),
    precio_descuento: Optional[float] = Form(None),
    costo_costura: Optional[float] = Form(None),
    costo_tapiceria: Optional[float] = Form(None),
    costo_esqueleteria: Optional[float] = Form(None),
    costo_armado: Optional[float] = Form(None),
    costo_corte: Optional[float] = Form(None),
    
    # Imágenes de proceso
    imagen_corte: Optional[UploadFile] = File(None),
    imagen_lapizado: Optional[UploadFile] = File(None),
    imagen_corte_esqueleto: Optional[UploadFile] = File(None),
    imagen_esqueleto: Optional[UploadFile] = File(None),
    
    # Imágenes de producto
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
    """Crear producto desde formulario HTML con manejo de archivos"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        
        # Procesar valores numéricos (convertir None a 0 si es necesario)
        precio_venta_final = precio_venta if precio_venta is not None else 0.0
        precio_descuento_final = precio_descuento if precio_descuento is not None else 0.0
        costo_costura_final = costo_costura if costo_costura is not None else 0.0
        costo_tapiceria_final = costo_tapiceria if costo_tapiceria is not None else 0.0
        costo_esqueleteria_final = costo_esqueleteria if costo_esqueleteria is not None else 0.0
        costo_armado_final = costo_armado if costo_armado is not None else 0.0
        costo_corte_final = costo_corte if costo_corte is not None else 0.0

        # Procesar producto_imagenes_venta_id
        producto_imagenes_venta_id_final = None
        if producto_imagenes_venta_id and producto_imagenes_venta_id.strip():
            try:
                producto_imagenes_venta_id_final = int(producto_imagenes_venta_id)
            except ValueError:
                producto_imagenes_venta_id_final = None

        # Insertar producto básico primero
        cursor.execute("""
            INSERT INTO productos (
                sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
                costo_costura, costo_tapiceria, costo_esqueleteria, costo_armado, costo_corte,
                precio_venta, precio_descuento, tipo_producto, descripcion_producto, material,
                colores_disponibles, tiempo_entrega, dimensiones, colores_hex,
                tipo_producto_venta, producto_imagenes_venta_id, visitas, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            sku, sku_esqueleto, sku_hites, sku_la_polar, nombre, esqueleto,
            costo_costura_final, costo_tapiceria_final, costo_esqueleteria_final, costo_armado_final, costo_corte_final,
            precio_venta_final, precio_descuento_final, tipo_producto, descripcion_producto, material,
            colores_disponibles, tiempo_entrega, dimensiones, colores_hex,
            tipo_producto_venta, producto_imagenes_venta_id_final, 0, datetime.now()
        ))
        
        producto_id = cursor.lastrowid
        conn.commit()
        
        # Procesar imágenes de proceso
        imagenes_proceso = {
            'imagen_corte': imagen_corte,
            'imagen_lapizado': imagen_lapizado,
            'imagen_corte_esqueleto': imagen_corte_esqueleto,
            'imagen_esqueleto': imagen_esqueleto
        }
        
        rutas_proceso = {}
        for campo, archivo in imagenes_proceso.items():
            if archivo and archivo.filename:
                # Generar nombre único
                extension = archivo.filename.split('.')[-1]
                nombre_archivo = f"{producto_id}_{campo}.{extension}"
                ruta_archivo = os.path.join(SHOW_IMG_PATH, nombre_archivo)
                
                # Guardar archivo
                with open(ruta_archivo, "wb") as buffer:
                    shutil.copyfileobj(archivo.file, buffer)
                
                rutas_proceso[campo] = f"/imagenes_jhk/show/{nombre_archivo}"
        
        # Procesar imágenes de producto
        imagenes_producto = {
            'img_1': img_1, 'img_2': img_2, 'img_3': img_3, 'img_4': img_4, 'img_5': img_5,
            'img_6': img_6, 'img_7': img_7, 'img_8': img_8, 'img_9': img_9, 'img_10': img_10
        }
        
        rutas_producto = {}
        for campo, archivo in imagenes_producto.items():
            if archivo and archivo.filename:
                # Generar nombre único
                extension = archivo.filename.split('.')[-1]
                nombre_archivo = f"{producto_id}_{campo}.{extension}"
                ruta_archivo = os.path.join(PRODUCTOS_IMG_PATH, nombre_archivo)
                
                # Guardar archivo
                with open(ruta_archivo, "wb") as buffer:
                    shutil.copyfileobj(archivo.file, buffer)
                
                rutas_producto[campo] = f"/imagenes_jhk/productos/{nombre_archivo}"
        
        # Actualizar base de datos con rutas de imágenes
        todas_las_rutas = {**rutas_proceso, **rutas_producto}
        
        if todas_las_rutas:
            set_clause = ", ".join([f"{campo} = %s" for campo in todas_las_rutas.keys()])
            valores = list(todas_las_rutas.values()) + [producto_id]
            
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE id = %s", valores)
            conn.commit()
        
        cursor.close()
        conn.close()
        
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
    precio_venta: Optional[float] = Form(None),
    descripcion_producto: str = Form(""),
    material: str = Form(""),
    colores_disponibles: str = Form(""),
    tiempo_entrega: str = Form(""),
    dimensiones: str = Form(""),
    costo_costura: Optional[float] = Form(None),
    costo_tapiceria: Optional[float] = Form(None),
    costo_esqueleteria: Optional[float] = Form(None),
    costo_armado: Optional[float] = Form(None),
    costo_corte: Optional[float] = Form(None),
    precio_descuento: Optional[float] = Form(None),
    sku_esqueleto: str = Form(""),
    sku_hites: str = Form(""),
    sku_la_polar: str = Form(""),
    esqueleto: str = Form(""),
    colores_hex: str = Form(""),
    tipo_producto_venta: str = Form(""),
    producto_imagenes_venta_id: Optional[str] = Form(""),

    # Campos para eliminar imágenes
    eliminar_img_1: Optional[str] = Form(None),
    eliminar_img_2: Optional[str] = Form(None),
    eliminar_img_3: Optional[str] = Form(None),
    eliminar_img_4: Optional[str] = Form(None),
    eliminar_img_5: Optional[str] = Form(None),
    eliminar_img_6: Optional[str] = Form(None),
    eliminar_img_7: Optional[str] = Form(None),
    eliminar_img_8: Optional[str] = Form(None),
    eliminar_img_9: Optional[str] = Form(None),
    eliminar_img_10: Optional[str] = Form(None),
    eliminar_imagen_corte: Optional[str] = Form(None),
    eliminar_imagen_lapizado: Optional[str] = Form(None),
    eliminar_imagen_corte_esqueleto: Optional[str] = Form(None),
    eliminar_imagen_esqueleto: Optional[str] = Form(None),

    # Nuevas imágenes
    img_1: Optional[UploadFile] = File(None),
    img_2: Optional[UploadFile] = File(None),
    img_3: Optional[UploadFile] = File(None),
    img_4: Optional[UploadFile] = File(None),
    img_5: Optional[UploadFile] = File(None),
    img_6: Optional[UploadFile] = File(None),
    img_7: Optional[UploadFile] = File(None),
    img_8: Optional[UploadFile] = File(None),
    img_9: Optional[UploadFile] = File(None),
    img_10: Optional[UploadFile] = File(None),
    imagen_corte: Optional[UploadFile] = File(None),
    imagen_lapizado: Optional[UploadFile] = File(None),
    imagen_corte_esqueleto: Optional[UploadFile] = File(None),
    imagen_esqueleto: Optional[UploadFile] = File(None)
):
    """Actualizar producto desde formulario HTML con manejo completo de archivos"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Obtener producto actual
        cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto_actual = cursor.fetchone()

        if not producto_actual:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Mapeo de campos de imagen y sus carpetas
        imagenes_config = {
            "img_1": PRODUCTOS_IMG_PATH, "img_2": PRODUCTOS_IMG_PATH,
            "img_3": PRODUCTOS_IMG_PATH, "img_4": PRODUCTOS_IMG_PATH,
            "img_5": PRODUCTOS_IMG_PATH, "img_6": PRODUCTOS_IMG_PATH,
            "img_7": PRODUCTOS_IMG_PATH, "img_8": PRODUCTOS_IMG_PATH,
            "img_9": PRODUCTOS_IMG_PATH, "img_10": PRODUCTOS_IMG_PATH,
            "imagen_corte": SHOW_IMG_PATH,
            "imagen_lapizado": SHOW_IMG_PATH,
            "imagen_corte_esqueleto": SHOW_IMG_PATH,
            "imagen_esqueleto": SHOW_IMG_PATH
        }

        # Procesar eliminaciones de imágenes
        campos_a_eliminar = []
        eliminar_flags = {
            'img_1': eliminar_img_1, 'img_2': eliminar_img_2, 'img_3': eliminar_img_3,
            'img_4': eliminar_img_4, 'img_5': eliminar_img_5, 'img_6': eliminar_img_6,
            'img_7': eliminar_img_7, 'img_8': eliminar_img_8, 'img_9': eliminar_img_9,
            'img_10': eliminar_img_10, 'imagen_corte': eliminar_imagen_corte,
            'imagen_lapizado': eliminar_imagen_lapizado, 
            'imagen_corte_esqueleto': eliminar_imagen_corte_esqueleto,
            'imagen_esqueleto': eliminar_imagen_esqueleto
        }

        for campo, eliminar_flag in eliminar_flags.items():
            if eliminar_flag and producto_actual.get(campo):
                carpeta = imagenes_config[campo]
                nombre_archivo = producto_actual[campo]
                if nombre_archivo:
                    # Extraer solo el nombre del archivo de la URL
                    nombre_archivo_limpio = nombre_archivo.split('/')[-1]
                    ruta_completa = Path(carpeta) / nombre_archivo_limpio
                    try:
                        if ruta_completa.exists():
                            ruta_completa.unlink()
                    except Exception as e:
                        print(f"Error al eliminar {ruta_completa}: {str(e)}")
                campos_a_eliminar.append(campo)

        # Eliminar referencias en base de datos
        if campos_a_eliminar:
            set_clause = ", ".join(f"{campo} = NULL" for campo in campos_a_eliminar)
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE id = %s", (producto_id,))
            conn.commit()

        # Procesar valores numéricos (convertir None a 0 si es necesario)
        precio_venta_final = precio_venta if precio_venta is not None else 0.0
        precio_descuento_final = precio_descuento if precio_descuento is not None else 0.0
        costo_costura_final = costo_costura if costo_costura is not None else 0.0
        costo_tapiceria_final = costo_tapiceria if costo_tapiceria is not None else 0.0
        costo_esqueleteria_final = costo_esqueleteria if costo_esqueleteria is not None else 0.0
        costo_armado_final = costo_armado if costo_armado is not None else 0.0
        costo_corte_final = costo_corte if costo_corte is not None else 0.0

        # Procesar producto_imagenes_venta_id
        producto_imagenes_venta_id_final = None
        if producto_imagenes_venta_id and producto_imagenes_venta_id.strip():
            try:
                producto_imagenes_venta_id_final = int(producto_imagenes_venta_id)
            except ValueError:
                producto_imagenes_venta_id_final = None

        # Actualizar datos básicos del producto
        cursor.execute("""
            UPDATE productos SET
                sku = %s, nombre = %s, tipo_producto = %s, precio_venta = %s,
                descripcion_producto = %s, material = %s, colores_disponibles = %s,
                tiempo_entrega = %s, dimensiones = %s, costo_costura = %s,
                costo_tapiceria = %s, costo_esqueleteria = %s, costo_armado = %s,
                costo_corte = %s, precio_descuento = %s, sku_esqueleto = %s,
                sku_hites = %s, sku_la_polar = %s, esqueleto = %s, colores_hex = %s,
                tipo_producto_venta = %s, producto_imagenes_venta_id = %s, updated_at = %s
            WHERE id = %s
        """, (
            sku, nombre, tipo_producto, precio_venta_final, descripcion_producto, material,
            colores_disponibles, tiempo_entrega, dimensiones, costo_costura_final,
            costo_tapiceria_final, costo_esqueleteria_final, costo_armado_final, costo_corte_final,
            precio_descuento_final, sku_esqueleto, sku_hites, sku_la_polar, esqueleto,
            colores_hex, tipo_producto_venta, producto_imagenes_venta_id_final,
            datetime.now(), producto_id
        ))
        conn.commit()

        # Procesar nuevas imágenes
        nuevas_imagenes = {
            "img_1": img_1, "img_2": img_2, "img_3": img_3, "img_4": img_4,
            "img_5": img_5, "img_6": img_6, "img_7": img_7, "img_8": img_8,
            "img_9": img_9, "img_10": img_10, "imagen_corte": imagen_corte,
            "imagen_lapizado": imagen_lapizado, "imagen_corte_esqueleto": imagen_corte_esqueleto,
            "imagen_esqueleto": imagen_esqueleto
        }

        campos_actualizados = {}
        for campo, archivo in nuevas_imagenes.items():
            if archivo and archivo.filename:
                # Generar nombre único
                extension = archivo.filename.split('.')[-1].lower()
                nombre_archivo = f"{producto_id}_{campo}.{extension}"
                carpeta = imagenes_config[campo]
                ruta_archivo = os.path.join(carpeta, nombre_archivo)
                
                # Guardar archivo
                with open(ruta_archivo, "wb") as buffer:
                    shutil.copyfileobj(archivo.file, buffer)
                
                # Generar URL según el tipo de imagen
                if 'img_' in campo:
                    url_archivo = f"/imagenes_jhk/productos/{nombre_archivo}"
                else:
                    url_archivo = f"/imagenes_jhk/show/{nombre_archivo}"
                
                campos_actualizados[campo] = url_archivo

        # Actualizar rutas de nuevas imágenes en base de datos
        if campos_actualizados:
            set_clause = ", ".join([f"{campo} = %s" for campo in campos_actualizados])
            valores = list(campos_actualizados.values()) + [producto_id]
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE id = %s", valores)
            conn.commit()

        cursor.close()
        conn.close()

        return RedirectResponse(url="/configuracion/productos/", status_code=303)

    except Exception as e:
        print(f"Error en actualizar_producto_form: {str(e)}")  # Para debug
        raise HTTPException(status_code=500, detail=f"Error al actualizar producto: {str(e)}")