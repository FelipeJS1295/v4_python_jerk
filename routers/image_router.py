from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import uuid
import shutil
from PIL import Image
from pathlib import Path
from typing import Optional

# Crear router
router = APIRouter()

# Configuración para desarrollo local
PROJECT_ROOT = Path.cwd()  # Directorio actual del proyecto
UPLOAD_DIR = PROJECT_ROOT / "static" / "images" / "productos"
THUMBNAILS_DIR = UPLOAD_DIR / "thumbnails"
TEMP_DIR = PROJECT_ROOT / "uploads" / "temp"
BASE_URL = "http://localhost:8000/images/productos"  # Puerto local típico de FastAPI

def ensure_directories():
    """Crear directorios necesarios"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Directorios creados en: {PROJECT_ROOT}")
    print(f"   - Upload: {UPLOAD_DIR}")
    print(f"   - Thumbnails: {THUMBNAILS_DIR}")
    print(f"   - Temp: {TEMP_DIR}")

def optimize_image(input_path: Path, output_path: Path, quality: int = 85, max_width: int = 1200) -> bool:
    """Optimizar imagen manteniendo calidad"""
    try:
        with Image.open(input_path) as img:
            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Redimensionar si es muy grande
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Guardar optimizada
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            return True
            
    except Exception as e:
        print(f"Error optimizando imagen: {e}")
        return False

def create_thumbnail(image_path: Path, thumb_path: Path, size: tuple = (300, 300)) -> bool:
    """Crear thumbnail de imagen"""
    try:
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, 'JPEG', quality=80, optimize=True)
            return True
            
    except Exception as e:
        print(f"Error creando thumbnail: {e}")
        return False

def validate_image_file(file: UploadFile) -> bool:
    """Validar archivo de imagen"""
    if not file.content_type or not file.content_type.startswith('image/'):
        return False
    
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_extension = Path(file.filename).suffix.lower()
    
    return file_extension in allowed_extensions

@router.post("/configuracion/productos/upload-image")
async def upload_product_image(
    image: UploadFile = File(...),
    product_id: str = Form(...)
):
    """Endpoint para subir imágenes de productos"""
    
    ensure_directories()
    
    print(f"📤 Subiendo imagen: {image.filename} para producto: {product_id}")
    
    if not validate_image_file(image):
        raise HTTPException(
            status_code=400, 
            detail="Formato de archivo no válido. Soportados: JPG, PNG, GIF, WEBP"
        )
    
    content = await image.read()
    
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=400, 
            detail="La imagen es demasiado grande (máximo 10MB)"
        )
    
    if len(content) == 0:
        raise HTTPException(
            status_code=400, 
            detail="El archivo está vacío"
        )
    
    temp_file = None
    final_file = None
    thumb_file = None
    
    try:
        file_extension = Path(image.filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:8]
        unique_filename = f"{product_id}_{unique_id}.jpg"
        
        temp_file = TEMP_DIR / f"temp_{unique_id}{file_extension}"
        final_file = UPLOAD_DIR / unique_filename
        thumb_file = THUMBNAILS_DIR / unique_filename
        
        print(f"💾 Guardando archivo como: {unique_filename}")
        
        # Guardar archivo temporal
        with open(temp_file, 'wb') as f:
            f.write(content)
        
        if not temp_file.exists() or temp_file.stat().st_size == 0:
            raise Exception("Error guardando archivo temporal")
        
        # Optimizar imagen
        if not optimize_image(temp_file, final_file):
            shutil.copy2(temp_file, final_file)
            print(f"⚠️ Optimización falló, usando archivo original")
        
        if not final_file.exists():
            raise Exception("Error guardando imagen final")
        
        # Crear thumbnail
        if not create_thumbnail(final_file, thumb_file):
            print(f"⚠️ No se pudo crear thumbnail")
        
        image_url = f"{BASE_URL}/{unique_filename}"
        thumbnail_url = f"{BASE_URL}/thumbnails/{unique_filename}" if thumb_file.exists() else None
        
        print(f"✅ Imagen guardada: {image_url}")
        
        return JSONResponse(content={
            "success": True,
            "url": image_url,
            "thumbnail_url": thumbnail_url,
            "filename": unique_filename,
            "size": final_file.stat().st_size,
            "message": "Imagen subida correctamente"
        })
        
    except Exception as e:
        print(f"❌ Error subiendo imagen: {e}")
        
        # Limpiar archivos en caso de error
        for file_path in [temp_file, final_file, thumb_file]:
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
        
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )
    
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

@router.delete("/configuracion/productos/delete-image/{filename}")
async def delete_product_image(filename: str):
    """Endpoint para eliminar imágenes"""
    try:
        print(f"🗑️ Eliminando imagen: {filename}")
        
        # Validar nombre de archivo
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
        
        # Solo permitir archivos .jpg
        if not filename.endswith('.jpg'):
            raise HTTPException(status_code=400, detail="Solo se permiten archivos .jpg")
        
        image_path = UPLOAD_DIR / filename
        thumb_path = THUMBNAILS_DIR / filename
        
        deleted_files = []
        
        if image_path.exists():
            image_path.unlink()
            deleted_files.append("imagen principal")
            print(f"🗑️ Eliminada imagen principal: {image_path}")
        
        if thumb_path.exists():
            thumb_path.unlink()
            deleted_files.append("thumbnail")
            print(f"🗑️ Eliminado thumbnail: {thumb_path}")
        
        if not deleted_files:
            print(f"ℹ️ Imagen {filename} no encontrada (posiblemente ya eliminada)")
            return JSONResponse(content={
                "success": True,
                "message": "Imagen no encontrada (posiblemente ya eliminada)",
                "deleted_files": []
            })
        
        print(f"✅ Eliminación completada: {deleted_files}")
        
        return JSONResponse(content={
            "success": True,
            "deleted_files": deleted_files,
            "message": f"Eliminados: {', '.join(deleted_files)}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error eliminando imagen: {e}")
        return JSONResponse(content={
            "success": False,
            "message": f"Error eliminando imagen: {str(e)}"
        })

@router.get("/configuracion/productos/storage-info")
async def get_storage_info():
    """Información de almacenamiento"""
    try:
        ensure_directories()
        
        total_images = 0
        total_size = 0
        total_thumbnails = 0
        
        if UPLOAD_DIR.exists():
            for image_file in UPLOAD_DIR.glob("*.jpg"):
                if image_file.is_file():
                    total_images += 1
                    total_size += image_file.stat().st_size
        
        if THUMBNAILS_DIR.exists():
            for thumb_file in THUMBNAILS_DIR.glob("*.jpg"):
                if thumb_file.is_file():
                    total_thumbnails += 1
                    total_size += thumb_file.stat().st_size
        
        print(f"📊 Storage info - Imágenes: {total_images}, Thumbnails: {total_thumbnails}, Tamaño: {total_size/1024/1024:.2f}MB")
        
        return JSONResponse(content={
            "success": True,
            "images": {
                "total_images": total_images,
                "total_thumbnails": total_thumbnails,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            },
            "directories": {
                "upload_dir": str(UPLOAD_DIR),
                "thumbnails_dir": str(THUMBNAILS_DIR),
                "temp_dir": str(TEMP_DIR),
                "base_url": BASE_URL
            }
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo info: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo información")

# Inicializar directorios al importar
ensure_directories()