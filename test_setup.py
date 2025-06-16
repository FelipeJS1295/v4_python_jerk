#!/usr/bin/env python3
"""
Script para verificar que todo está configurado correctamente
"""

import os
import sys
from pathlib import Path

def check_directories():
    """Verificar que existen los directorios necesarios"""
    print("📁 Verificando directorios...")
    
    required_dirs = [
        "static/images/productos",
        "static/images/productos/thumbnails",
        "uploads/temp"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ❌ {dir_path} - FALTA")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Verificar dependencias"""
    print("\n📦 Verificando dependencias...")
    
    try:
        from PIL import Image
        print("   ✅ Pillow (PIL)")
    except ImportError:
        print("   ❌ Pillow - Instala con: pip install Pillow")
        return False
    
    try:
        from fastapi import FastAPI
        print("   ✅ FastAPI")
    except ImportError:
        print("   ❌ FastAPI")
        return False
    
    try:
        from fastapi.staticfiles import StaticFiles
        print("   ✅ StaticFiles")
    except ImportError:
        print("   ❌ StaticFiles")
        return False
    
    return True

def check_router_file():
    """Verificar que existe el router de imágenes"""
    print("\n🔧 Verificando router de imágenes...")
    
    router_path = Path("routers/image_router.py")
    if router_path.exists():
        print("   ✅ routers/image_router.py existe")
        
        # Verificar contenido básico
        with open(router_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'upload_product_image' in content:
            print("   ✅ Función upload_product_image encontrada")
        else:
            print("   ❌ Función upload_product_image no encontrada")
            return False
            
        if 'delete_product_image' in content:
            print("   ✅ Función delete_product_image encontrada")
        else:
            print("   ❌ Función delete_product_image no encontrada")
            return False
        
        return True
    else:
        print("   ❌ routers/image_router.py NO EXISTE")
        return False

def check_main_py():
    """Verificar configuración en main.py"""
    print("\n⚙️ Verificando main.py...")
    
    main_path = Path("main.py")
    if not main_path.exists():
        print("   ❌ main.py no encontrado")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('image_router', 'Import del router de imágenes'),
        ('app.include_router(image_router.router)', 'Include del router de imágenes'),
        ('app.mount("/images"', 'Mount de archivos de imágenes'),
    ]
    
    all_good = True
    for check, description in checks:
        if check in content:
            print(f"   ✅ {description}")
        else:
            print(f"   ❌ {description} - FALTA")
            all_good = False
    
    return all_good

def create_missing_files():
    """Crear archivos faltantes"""
    print("\n🔨 Creando archivos faltantes...")
    
    # Crear directorios si no existen
    dirs_to_create = [
        "static/images/productos",
        "static/images/productos/thumbnails",
        "uploads/temp"
    ]
    
    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"   📁 {dir_path}")
    
    # Crear archivo .gitkeep en uploads/temp para mantener el directorio en git
    gitkeep_path = Path("uploads/temp/.gitkeep")
    if not gitkeep_path.exists():
        gitkeep_path.touch()
        print("   📄 uploads/temp/.gitkeep")

def show_main_py_additions():
    """Mostrar qué agregar a main.py"""
    print("\n📝 AGREGAR A main.py:")
    print("-" * 40)
    
    print("1. En la sección de imports de routers:")
    print("   from routers import image_router")
    
    print("\n2. Después de app.mount('/static', ...):")
    print('   app.mount("/images", StaticFiles(directory="static/images"), name="images")')
    
    print("\n3. Con los otros app.include_router(...):")
    print("   app.include_router(image_router.router)")

def main():
    """Función principal"""
    print("🔍 VERIFICANDO CONFIGURACIÓN DE IMÁGENES")
    print("=" * 50)
    
    # Verificaciones
    dirs_ok = check_directories()
    deps_ok = check_dependencies()
    router_ok = check_router_file()
    main_ok = check_main_py()
    
    print("\n" + "=" * 50)
    print("📋 RESUMEN:")
    
    if dirs_ok and deps_ok and router_ok and main_ok:
        print("✅ TODO CONFIGURADO CORRECTAMENTE")
        print("\n🚀 SIGUIENTE PASO:")
        print("   uvicorn main:app --reload --port 8000")
        print("   Luego abre: http://localhost:8000/configuracion/productos/")
    else:
        print("❌ FALTAN CONFIGURACIONES")
        
        if not dirs_ok:
            create_missing_files()
        
        if not router_ok:
            print("\n❗ CREAR routers/image_router.py con el código proporcionado")
        
        if not main_ok:
            show_main_py_additions()
        
        if not deps_ok:
            print("\n❗ INSTALAR DEPENDENCIAS:")
            print("   pip install Pillow")

if __name__ == "__main__":
    main()