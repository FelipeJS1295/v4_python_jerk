from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os
from db import conectar_mysql
from datetime import date, timedelta
from typing import Optional
import pandas as pd
import re
from mysql.connector import connect
from fastapi import UploadFile, File
import io
from datetime import datetime, date
import traceback
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
from pydantic import BaseModel
import logging


router = APIRouter(prefix="/finanzas", tags=["Finanzas"])

# Configurar templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters['dd_mm_yyyy'] = lambda fecha: fecha.strftime('%d-%m-%Y') if fecha else ''


def obtener_conexion():
    """Usar la función centralizada de db.py"""
    from db import conectar_mysql
    return conectar_mysql()

def convertir_parametros_seguros(request: Request):
    """Convierte los parámetros de query de manera segura"""
    query_params = request.query_params
    
    # Proveedor y estado (ya son strings, no hay problema)
    proveedor = query_params.get('proveedor') or None
    estado = query_params.get('estado') or None
    orden = query_params.get('orden') or "fecha_vencimiento_asc"
    
    # Fechas - convertir de string a date de manera segura
    fecha_desde = None
    if query_params.get('fecha_desde'):
        try:
            from datetime import datetime
            fecha_desde = datetime.strptime(query_params.get('fecha_desde'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    fecha_hasta = None
    if query_params.get('fecha_hasta'):
        try:
            from datetime import datetime
            fecha_hasta = datetime.strptime(query_params.get('fecha_hasta'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Montos - convertir de string a int de manera segura
    monto_min = None
    if query_params.get('monto_min'):
        try:
            monto_min = int(float(query_params.get('monto_min')))
        except (ValueError, TypeError):
            pass
    
    monto_max = None
    if query_params.get('monto_max'):
        try:
            monto_max = int(float(query_params.get('monto_max')))
        except (ValueError, TypeError):
            pass
    
    return proveedor, estado, fecha_desde, fecha_hasta, monto_min, monto_max, orden

# Calcular días vencido
def calcular_dias_vencido(fecha_vencimiento):
    hoy = date.today()
    if fecha_vencimiento < hoy:
        return (hoy - fecha_vencimiento).days
    return 0

# Función para calcular faltante de una factura (SOLO ENTEROS)
def calcular_faltante_factura(cursor, factura_id, total_factura):
    cursor.execute(
        "SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", 
        (factura_id,)
    )
    resultado = cursor.fetchone()
    total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
    faltante = int(total_factura) - total_pagado
    return max(0, faltante)  # Siempre retorna entero, no negativo

# Mostrar listado de facturas con filtros
@router.get("/", response_class=HTMLResponse)
def listar_facturas(request: Request):  # <-- SOLO CAMBIO AQUÍ: quitar todos los parámetros Query
    
    # AGREGAR SOLO ESTA LÍNEA AL INICIO:
    proveedor, estado, fecha_desde, fecha_hasta, monto_min, monto_max, orden = convertir_parametros_seguros(request)
    
    # === EL RESTO DE TU CÓDIGO QUEDA EXACTAMENTE IGUAL ===
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # === MÉTRICAS DEL DASHBOARD (sin filtros) ===
        
        # Total de facturas y montos generales
        cursor.execute("""
            SELECT 
                COUNT(*) as total_facturas_sistema,
                COALESCE(SUM(total), 0) as total_monto_sistema
            FROM facturas_compra
        """)
        metricas_sistema = cursor.fetchone()
        
        # Calcular facturas vencidas y deuda pendiente
        from datetime import date
        hoy = date.today()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_vencidas,
                COALESCE(SUM(total), 0) as deuda_vencida
            FROM facturas_compra fc
            WHERE fc.fecha_vencimiento < %s
        """, (hoy,))
        metricas_vencidas = cursor.fetchone()
        
        # Deuda por proveedor (Top 10)
        cursor.execute("""
            SELECT 
                p.nombre,
                COUNT(fc.id) as facturas_pendientes,
                COALESCE(SUM(fc.total), 0) as deuda_total,
                COALESCE(SUM(CASE 
                    WHEN fc.fecha_vencimiento < %s 
                    THEN 1 ELSE 0 
                END), 0) as vencidas
            FROM proveedores p
            INNER JOIN facturas_compra fc ON p.id = fc.proveedor_id
            WHERE fc.total > 0
            GROUP BY p.id, p.nombre
            HAVING deuda_total > 0
            ORDER BY deuda_total DESC
            LIMIT 10
        """, (hoy,))
        deuda_por_proveedor = cursor.fetchall()
        
        # === CONSULTA PRINCIPAL DE FACTURAS (con filtros) ===
        
        # Query base
        query = """
            SELECT fc.id, fc.numero_documento, p.nombre AS proveedor, 
                   fc.fecha_documento, fc.fecha_vencimiento, fc.total
            FROM facturas_compra fc
            JOIN proveedores p ON fc.proveedor_id = p.id
            WHERE 1=1
        """
        params = []
        
        # Filtro por proveedor
        if proveedor:
            query += " AND p.nombre LIKE %s"
            params.append(f"%{proveedor}%")
        
        # Filtro por fechas
        if fecha_desde:
            query += " AND fc.fecha_vencimiento >= %s"
            params.append(fecha_desde)
        
        if fecha_hasta:
            query += " AND fc.fecha_vencimiento <= %s"
            params.append(fecha_hasta)
        
        # Filtro por montos
        if monto_min:
            query += " AND fc.total >= %s"
            params.append(monto_min)
        
        if monto_max:
            query += " AND fc.total <= %s"
            params.append(monto_max)
        
        # Ordenamiento
        orden_map = {
            "fecha_vencimiento_asc": "fc.fecha_vencimiento ASC",
            "fecha_vencimiento_desc": "fc.fecha_vencimiento DESC",
            "monto_asc": "fc.total ASC",
            "monto_desc": "fc.total DESC",
            "proveedor": "p.nombre ASC"
        }
        
        if orden in orden_map:
            query += f" ORDER BY {orden_map[orden]}"
        else:
            query += " ORDER BY fc.fecha_vencimiento ASC"
        
        # Limitar resultados para performance
        query += " LIMIT 1000"
        
        cursor.execute(query, params)
        facturas = cursor.fetchall()
        
        # Calcular días vencido, faltante y aplicar filtro de estado
        facturas_filtradas = []
        
        for f in facturas:
            f["dias_vencido"] = calcular_dias_vencido(f["fecha_vencimiento"])
            f["faltante"] = calcular_faltante_factura(cursor, f["id"], f["total"])
            f["total"] = int(f["total"])  # Asegurar que total sea entero
            
            # Filtro por estado
            if estado:
                if estado == "vencido" and f["dias_vencido"] <= 0:
                    continue
                elif estado == "al_dia" and f["dias_vencido"] > 0:
                    continue
                elif estado == "por_vencer":
                    dias_hasta_vencimiento = (f["fecha_vencimiento"] - hoy).days
                    if dias_hasta_vencimiento < 0 or dias_hasta_vencimiento > 7:
                        continue
                elif estado == "pagado" and f["faltante"] > 0:
                    continue
                elif estado == "pendiente" and f["faltante"] <= 0:
                    continue
            
            # Formatear montos para mostrar
            f["total_formatted"] = formatear_pesos(f["total"])
            f["faltante_formatted"] = formatear_pesos(f["faltante"])
            
            facturas_filtradas.append(f)
        
        # Calcular totales de la búsqueda actual (filtrada)
        total_facturas_filtradas = len(facturas_filtradas)
        total_monto_filtrado = sum(f["total"] for f in facturas_filtradas)
        total_faltante_filtrado = sum(f["faltante"] for f in facturas_filtradas)
        
        # Formatear montos para deuda por proveedor
        for proveedor_data in deuda_por_proveedor:
            proveedor_data['deuda_total_formatted'] = formatear_pesos(proveedor_data['deuda_total'])
        
        # Calcular deuda total del sistema (aproximada)
        total_deuda_sistema = sum(f["faltante"] for f in facturas_filtradas) if facturas_filtradas else metricas_vencidas['deuda_vencida']
        
    except Exception as e:
        print(f"Error en consulta: {e}")
        # Valores por defecto en caso de error
        facturas_filtradas = []
        deuda_por_proveedor = []
        metricas_sistema = {'total_facturas_sistema': 0, 'total_monto_sistema': 0}
        metricas_vencidas = {'total_vencidas': 0, 'deuda_vencida': 0}
        total_facturas_filtradas = 0
        total_monto_filtrado = 0
        total_faltante_filtrado = 0
        total_deuda_sistema = 0
    
    finally:
        cursor.close()
        conn.close()
    
    # Preparar contexto para el template
    context = {
        "request": request,
        "facturas": facturas_filtradas,
        
        # === MÉTRICAS DEL DASHBOARD ===
        "total_facturas": metricas_sistema['total_facturas_sistema'],
        "total_monto": formatear_pesos(metricas_sistema['total_monto_sistema']),
        "total_vencidas": metricas_vencidas['total_vencidas'],
        "total_faltante": formatear_pesos(total_deuda_sistema),
        "deuda_por_proveedor": deuda_por_proveedor,
        
        # === TOTALES DE LA BÚSQUEDA ACTUAL ===
        "total_facturas_filtradas": total_facturas_filtradas,
        "total_monto_filtrado": formatear_pesos(total_monto_filtrado),
        "total_faltante_filtrado": formatear_pesos(total_faltante_filtrado),
    }
    
    return templates.TemplateResponse("finanzas/index.html", context)

# Mostrar detalle de factura (SOLO ENTEROS)
@router.get("/factura/{factura_id}", response_class=HTMLResponse)
def detalle_factura(request: Request, factura_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener factura
        cursor.execute("""
            SELECT fc.*, p.nombre AS proveedor
            FROM facturas_compra fc
            JOIN proveedores p ON fc.proveedor_id = p.id
            WHERE fc.id = %s
        """, (factura_id,))
        factura = cursor.fetchone()
        
        if not factura:
            # Manejar factura no encontrada
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Factura no encontrada"
            })
        
        # AGREGAR ESTOS CÁLCULOS:
        
        # Calcular días vencido
        factura["dias_vencido"] = calcular_dias_vencido(factura["fecha_vencimiento"])
        
        # Obtener pagos
        cursor.execute("""
            SELECT * FROM pagos_factura 
            WHERE factura_id = %s 
            ORDER BY fecha DESC
        """, (factura_id,))
        pagos = cursor.fetchall()
        
        # Calcular totales
        total_pagado = sum(pago["monto"] for pago in pagos) if pagos else 0
        faltante = factura["total"] - total_pagado
        
        # Formatear fechas si es necesario
        from datetime import date
        
        context = {
            "request": request,
            "factura": factura,
            "pagos": pagos,
            "total_pagado": total_pagado,
            "faltante": faltante,
            "date": date  # Para usar date.today() en template
        }
        
        return templates.TemplateResponse("finanzas/detalle_factura.html", context)
        
    except Exception as e:
        print(f"Error en detalle_factura: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Error al cargar la factura"
        })
    
    finally:
        cursor.close()
        conn.close()

# Agregar pago (SOLO ENTEROS)
@router.post("/factura/{factura_id}/agregar-pago")
def agregar_pago(
    factura_id: int,
    tipo: str = Form(...),
    numero: str = Form(...),
    fecha: date = Form(...),
    monto: int = Form(...),
    estado: str = Form(default="pendiente")  # 👈 nuevo parámetro
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener información de la factura
        cursor.execute("SELECT total FROM facturas_compra WHERE id = %s", (factura_id,))
        factura = cursor.fetchone()
        
        if not factura:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=factura_no_encontrada", status_code=303)
        
        # Calcular total pagado actual
        cursor.execute("SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", (factura_id,))
        resultado = cursor.fetchone()
        total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
        
        faltante = int(factura["total"]) - total_pagado

        # Validaciones
        if monto <= 0:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=monto_invalido", status_code=303)
        
        if monto > faltante:
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=monto_excede_faltante", status_code=303)
        
        if not numero.strip():
            cursor.close()
            conn.close()
            return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=numero_requerido", status_code=303)
        
        # Insertar el pago con estado incluido
        cursor.execute("""
            INSERT INTO pagos_factura (factura_id, tipo, numero, monto, fecha, estado)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (factura_id, tipo, numero.strip(), monto, fecha, estado))
        
        # Calcular nuevo faltante
        nuevo_faltante = faltante - monto

        # Actualizar estado de la factura
        if nuevo_faltante <= 0:
            nuevo_estado = "pagada"
        else:
            cursor.execute("SELECT fecha_vencimiento FROM facturas_compra WHERE id = %s", (factura_id,))
            fecha_venc = cursor.fetchone()["fecha_vencimiento"]
            dias_vencido = calcular_dias_vencido(fecha_venc)
            nuevo_estado = "vencida" if dias_vencido > 0 else "pendiente"
        
        cursor.execute("""
            UPDATE facturas_compra 
            SET estado = %s, updated_at = NOW() 
            WHERE id = %s
        """, (nuevo_estado, factura_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?success=pago_agregado", status_code=303)
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=error_interno", status_code=303)

# Eliminar pago
@router.get("/factura/{factura_id}/eliminar-pago/{pago_id}")
def eliminar_pago(factura_id: int, pago_id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Eliminar el pago
        cursor.execute("DELETE FROM pagos_factura WHERE id = %s", (pago_id,))
        
        # Recalcular el estado después de eliminar el pago
        cursor.execute("SELECT total, fecha_vencimiento FROM facturas_compra WHERE id = %s", (factura_id,))
        factura = cursor.fetchone()
        
        # Calcular nuevo total pagado
        cursor.execute("SELECT COALESCE(SUM(monto), 0) as total_pagado FROM pagos_factura WHERE factura_id = %s", (factura_id,))
        resultado = cursor.fetchone()
        total_pagado = int(resultado["total_pagado"]) if resultado["total_pagado"] else 0
        
        # Calcular faltante
        faltante = int(factura["total"]) - total_pagado
        
        # Determinar nuevo estado
        if faltante <= 0:
            nuevo_estado = "pagada"
        else:
            dias_vencido = calcular_dias_vencido(factura["fecha_vencimiento"])
            if dias_vencido > 0:
                nuevo_estado = "vencida"
            else:
                nuevo_estado = "pendiente"
        
        # Actualizar estado
        cursor.execute("""
            UPDATE facturas_compra 
            SET estado = %s, updated_at = NOW() 
            WHERE id = %s
        """, (nuevo_estado, factura_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}", status_code=303)
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return RedirectResponse(url=f"/finanzas/factura/{factura_id}?error=error_eliminacion", status_code=303)

# Función para sincronizar estados de todas las facturas (ejecutar una vez)
@router.get("/sincronizar-estados")
def sincronizar_estados():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener todas las facturas
        cursor.execute("SELECT id, total, fecha_vencimiento FROM facturas_compra")
        facturas = cursor.fetchall()
        
        for factura in facturas:
            # Calcular faltante
            faltante = calcular_faltante_factura(cursor, factura["id"], factura["total"])
            
            # Determinar estado correcto
            if faltante <= 0:
                nuevo_estado = "pagada"
            else:
                dias_vencido = calcular_dias_vencido(factura["fecha_vencimiento"])
                if dias_vencido > 0:
                    nuevo_estado = "vencida"
                else:
                    nuevo_estado = "pendiente"
            
            # Actualizar estado
            cursor.execute("""
                UPDATE facturas_compra 
                SET estado = %s, updated_at = NOW() 
                WHERE id = %s
            """, (nuevo_estado, factura["id"]))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"message": "Estados sincronizados correctamente"}
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return {"error": str(e)}

def normalizar_rut(rut):
    """Elimina puntos del RUT y deja solo guion."""
    if not rut or pd.isna(rut):
        return ""
    
    rut_str = str(rut).strip()
    # Eliminar puntos y espacios
    rut_limpio = re.sub(r'[.\s]', '', rut_str)
    
    return rut_limpio

def validar_rut(rut):
    """Valida que el RUT tenga un formato válido chileno."""
    if not rut:
        return False
    
    # Patrón para RUT chileno: 7-8 dígitos, guión, dígito verificador
    patron = r'^\d{7,8}-[\dkK]$'
    return bool(re.match(patron, rut))

@router.get("/cargar-facturas/", response_class=HTMLResponse)
def cargar_facturas_page(request: Request):
    return templates.TemplateResponse("finanzas/cargar_facturas.html", {"request": request})

@router.post("/importar-facturas-sii/", response_class=HTMLResponse)
async def importar_facturas_sii_view(
    request: Request,
    file: UploadFile = File(...)
):
    try:
        # 1. Leer archivo
        content = await file.read()
        
        if file.filename.endswith(".csv"):
            # Decodificar el contenido probando diferentes encodings
            content_str = None
            for encoding in ['utf-8', 'ISO-8859-1', 'latin1', 'cp1252']:
                try:
                    content_str = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content_str is None:
                return templates.TemplateResponse("finanzas/cargar_facturas.html", {
                    "request": request,
                    "error": "⚠️ No se pudo decodificar el archivo. Verifica el formato."
                })
            
            # MÉTODO ALTERNATIVO: Leer línea por línea y procesar manualmente
            lines = content_str.strip().split('\n')
            
            if len(lines) < 2:
                return templates.TemplateResponse("finanzas/cargar_facturas.html", {
                    "request": request,
                    "error": "⚠️ El archivo está vacío o no tiene datos."
                })
            
            # Obtener headers
            headers = [h.strip() for h in lines[0].split(';')]
            print(f"=== HEADERS DETECTADOS ===")
            for i, header in enumerate(headers):
                print(f"{i}: '{header}'")
            
            # Verificar que tenemos las columnas necesarias
            try:
                idx_rut = headers.index('RUT Proveedor')
                idx_razon = headers.index('Razon Social')
                idx_folio = headers.index('Folio')
                idx_fecha = headers.index('Fecha Docto')
                idx_neto = headers.index('Monto Neto')
                idx_iva = headers.index('Monto IVA Recuperable')
                idx_total = headers.index('Monto Total')
            except ValueError as e:
                return templates.TemplateResponse("finanzas/cargar_facturas.html", {
                    "request": request,
                    "error": f"⚠️ Columna requerida no encontrada. Headers disponibles: {', '.join(headers)}"
                })
            
            print(f"Índices: RUT={idx_rut}, Razón={idx_razon}, Folio={idx_folio}")
            
        elif file.filename.endswith(".xlsx"):
            # Para Excel, usar pandas normalmente
            df = pd.read_excel(io.BytesIO(content), dtype=str)
            # Convertir a líneas para procesamiento uniforme
            lines = []
            lines.append(';'.join(df.columns))
            for _, row in df.iterrows():
                lines.append(';'.join([str(val) if not pd.isna(val) else '' for val in row.values]))
            
            headers = list(df.columns)
            try:
                idx_rut = headers.index('RUT Proveedor')
                idx_razon = headers.index('Razon Social')
                idx_folio = headers.index('Folio')
                idx_fecha = headers.index('Fecha Docto')
                idx_neto = headers.index('Monto Neto')
                idx_iva = headers.index('Monto IVA Recuperable')
                idx_total = headers.index('Monto Total')
            except ValueError:
                return templates.TemplateResponse("finanzas/cargar_facturas.html", {
                    "request": request,
                    "error": f"⚠️ Columna requerida no encontrada en Excel. Headers disponibles: {', '.join(headers)}"
                })
        else:
            return templates.TemplateResponse("finanzas/cargar_facturas.html", {
                "request": request,
                "error": "⚠️ Formato no válido. Solo se aceptan archivos .csv o .xlsx"
            })

        # 2. Conectar a BD
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)

        facturas_guardadas = []
        proveedores_nuevos = []
        errores = []
        facturas_existentes = []  # Nueva lista para facturas que ya existen

        # 3. Procesar líneas de datos (saltando el header)
        for line_num, line in enumerate(lines[1:], start=2):
            try:
                # Dividir la línea por punto y coma
                campos = [campo.strip() for campo in line.split(';')]
                
                print(f"\n=== PROCESANDO LÍNEA {line_num} ===")
                print(f"Línea completa: {line}")
                print(f"Campos divididos: {campos}")
                print(f"Total campos: {len(campos)}")
                
                # Verificar que tenemos suficientes campos
                if len(campos) <= max(idx_rut, idx_razon, idx_folio, idx_fecha, idx_neto, idx_iva, idx_total):
                    errores.append(f"Fila {line_num}: Línea incompleta - faltan campos")
                    continue
                
                # Extraer campos por índice
                rut_excel = normalizar_rut(campos[idx_rut])
                razon_social = campos[idx_razon]
                folio = campos[idx_folio]
                fecha_str = campos[idx_fecha]
                neto_str = campos[idx_neto]
                iva_str = campos[idx_iva]
                total_str = campos[idx_total]
                
                print(f"RUT extraído: '{rut_excel}' (posición {idx_rut})")
                print(f"Razón Social extraída: '{razon_social}' (posición {idx_razon})")
                print(f"Folio: '{folio}'")
                
                # Verificar que tenemos datos válidos
                if not rut_excel or not razon_social:
                    errores.append(f"Fila {line_num}: RUT o Razón Social vacíos")
                    continue
                
                # Validar formato del RUT
                if not validar_rut(rut_excel):
                    errores.append(f"Fila {line_num}: RUT no válido '{rut_excel}'")
                    print(f"❌ RUT inválido: '{rut_excel}'")
                    continue
                
                print(f"✅ RUT válido: '{rut_excel}'")

                # Buscar proveedor por RUT
                cursor.execute("SELECT id, rut FROM proveedores")
                proveedores = cursor.fetchall()

                proveedor_id = None
                for proveedor in proveedores:
                    rut_bd = normalizar_rut(proveedor["rut"])
                    if rut_bd == rut_excel:
                        proveedor_id = proveedor["id"]
                        break

                if not proveedor_id:
                    # Verificar si ya está en la lista de proveedores nuevos
                    existe_en_nuevos = any(p["rut"] == rut_excel for p in proveedores_nuevos)
                    if not existe_en_nuevos:
                        proveedores_nuevos.append({
                            "rut": rut_excel,
                            "razon_social": razon_social
                        })
                    print(f"⚠️ Proveedor no encontrado: {rut_excel}")
                    continue

                print(f"✅ Proveedor encontrado: ID {proveedor_id}")
                
                # Procesar fecha
                try:
                    fecha_documento = pd.to_datetime(fecha_str, format='%d/%m/%Y', errors='coerce').date()
                    if pd.isna(fecha_documento):
                        fecha_documento = pd.to_datetime(fecha_str, errors='coerce').date()
                except:
                    fecha_documento = None

                # Procesar montos
                try:
                    neto = float(neto_str.replace(',', '.')) if neto_str and neto_str != '' else 0
                    iva = float(iva_str.replace(',', '.')) if iva_str and iva_str != '' else 0
                    total = float(total_str.replace(',', '.')) if total_str and total_str != '' else neto + iva
                except Exception as e:
                    errores.append(f"Fila {line_num}: Error en montos - {str(e)}")
                    continue

                # Verificar si la factura ya existe
                cursor.execute("""
                    SELECT id FROM facturas_compra 
                    WHERE proveedor_id = %s AND numero_documento = %s
                """, (proveedor_id, folio))
                
                if cursor.fetchone():
                    facturas_existentes.append({
                        "folio": folio,
                        "rut": rut_excel,
                        "razon_social": razon_social
                    })
                    print(f"ℹ️ Factura ya existe: {folio}")
                    continue

                # Calcular fecha de vencimiento (30 días después de la fecha del documento por defecto)
                if fecha_documento:
                    from datetime import timedelta
                    fecha_vencimiento = fecha_documento + timedelta(days=30)
                else:
                    from datetime import date, timedelta
                    fecha_vencimiento = date.today() + timedelta(days=30)

                # Guardar factura
                cursor.execute("""
                    INSERT INTO facturas_compra (proveedor_id, numero_documento, fecha_documento, fecha_vencimiento, neto, iva, total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (proveedor_id, folio, fecha_documento, fecha_vencimiento, neto, iva, total))
                conn.commit()

                facturas_guardadas.append(folio)
                print(f"✅ Factura guardada: {folio}")

            except Exception as e:
                errores.append(f"Fila {line_num}: Error general - {str(e)}")
                print(f"❌ Error en línea {line_num}: {str(e)}")
                continue

        cursor.close()
        conn.close()

        # 4. Preparar mensaje de resultado
        mensaje_resultado = ""
        if facturas_guardadas:
            mensaje_resultado += f"✅ Se guardaron {len(facturas_guardadas)} facturas nuevas. "
        if facturas_existentes:
            mensaje_resultado += f"ℹ️ Se encontraron {len(facturas_existentes)} facturas que ya existen. "
        if proveedores_nuevos:
            mensaje_resultado += f"⚠️ Se encontraron {len(proveedores_nuevos)} proveedores nuevos que deben ser creados. "
        if errores:
            mensaje_resultado += f"❌ Se encontraron {len(errores)} errores."

        # 5. Mostrar resultados
        return templates.TemplateResponse("finanzas/cargar_facturas.html", {
            "request": request,
            "facturas_guardadas": facturas_guardadas,
            "facturas_existentes": facturas_existentes,  # Nueva variable
            "proveedores_faltantes": proveedores_nuevos,
            "mensaje_resultado": mensaje_resultado,
            "errores": errores[:20]  # Mostrar solo los primeros 20 errores
        })

    except Exception as e:
        print(f"Error general en importación: {str(e)}")
        return templates.TemplateResponse("finanzas/cargar_facturas.html", {
            "request": request,
            "error": f"⚠️ Error al procesar el archivo: {str(e)}"
        })

@router.get("/crear-proveedores/", response_class=HTMLResponse)
def crear_proveedores_page(request: Request):
    """Página para crear proveedores faltantes"""
    return templates.TemplateResponse("finanzas/crear_proveedores.html", {"request": request})

@router.post("/mostrar-proveedores-faltantes/", response_class=HTMLResponse)
async def mostrar_proveedores_faltantes(
    request: Request,
    file: UploadFile = File(...)
):
    """Analiza el archivo y muestra los proveedores que faltan"""
    try:
        # Reutilizar la lógica de lectura del archivo
        content = await file.read()
        
        if file.filename.endswith(".csv"):
            # Decodificar el contenido
            content_str = None
            for encoding in ['utf-8', 'ISO-8859-1', 'latin1', 'cp1252']:
                try:
                    content_str = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content_str is None:
                return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                    "request": request,
                    "error": "⚠️ No se pudo decodificar el archivo."
                })
            
            lines = content_str.strip().split('\n')
            
            if len(lines) < 2:
                return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                    "request": request,
                    "error": "⚠️ El archivo está vacío o no tiene datos."
                })
            
            # Obtener headers y índices
            headers = [h.strip() for h in lines[0].split(';')]
            try:
                idx_rut = headers.index('RUT Proveedor')
                idx_razon = headers.index('Razon Social')
            except ValueError:
                return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                    "request": request,
                    "error": f"⚠️ Columnas requeridas no encontradas. Headers: {', '.join(headers)}"
                })
            
        elif file.filename.endswith(".xlsx"):
            # Para Excel
            df = pd.read_excel(io.BytesIO(content), dtype=str)
            lines = []
            lines.append(';'.join(df.columns))
            for _, row in df.iterrows():
                lines.append(';'.join([str(val) if not pd.isna(val) else '' for val in row.values]))
            
            headers = list(df.columns)
            try:
                idx_rut = headers.index('RUT Proveedor')
                idx_razon = headers.index('Razon Social')
            except ValueError:
                return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                    "request": request,
                    "error": f"⚠️ Columnas requeridas no encontradas en Excel."
                })
        else:
            return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                "request": request,
                "error": "⚠️ Formato no válido. Solo se aceptan archivos .csv o .xlsx"
            })

        # Conectar a BD y obtener proveedores existentes
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT rut FROM proveedores")
        proveedores_existentes = [normalizar_rut(p["rut"]) for p in cursor.fetchall()]
        
        # Analizar archivo y encontrar proveedores faltantes
        proveedores_faltantes = []
        ruts_procesados = set()
        
        for line_num, line in enumerate(lines[1:], start=2):
            try:
                campos = [campo.strip() for campo in line.split(';')]
                
                if len(campos) <= max(idx_rut, idx_razon):
                    continue
                
                rut_excel = normalizar_rut(campos[idx_rut])
                razon_social = campos[idx_razon]
                
                # Validar RUT
                if not validar_rut(rut_excel):
                    continue
                
                # Si ya procesamos este RUT, saltar
                if rut_excel in ruts_procesados:
                    continue
                
                ruts_procesados.add(rut_excel)
                
                # Si no existe en BD, agregarlo a faltantes
                if rut_excel not in proveedores_existentes:
                    proveedores_faltantes.append({
                        "rut": rut_excel,
                        "nombre": razon_social
                    })
                    
            except Exception:
                continue
        
        cursor.close()
        conn.close()
        
        return templates.TemplateResponse("finanzas/crear_proveedores.html", {
            "request": request,
            "proveedores_faltantes": proveedores_faltantes,
            "total_faltantes": len(proveedores_faltantes)
        })
        
    except Exception as e:
        return templates.TemplateResponse("finanzas/crear_proveedores.html", {
            "request": request,
            "error": f"⚠️ Error al procesar el archivo: {str(e)}"
        })

@router.post("/crear-proveedores-seleccionados/", response_class=HTMLResponse)
async def crear_proveedores_seleccionados(request: Request):
    """Crea los proveedores que fueron seleccionados"""
    try:
        # Obtener datos del formulario
        form_data = await request.form()
        
        # Obtener los RUTs seleccionados
        ruts_seleccionados = form_data.getlist("proveedores_seleccionados")
        
        if not ruts_seleccionados:
            return templates.TemplateResponse("finanzas/crear_proveedores.html", {
                "request": request,
                "error": "⚠️ No se seleccionaron proveedores para crear."
            })
        
        # Conectar a BD
        conn = obtener_conexion()
        cursor = conn.cursor(dictionary=True)
        
        proveedores_creados = []
        errores = []
        
        for rut in ruts_seleccionados:
            try:
                # Obtener el nombre del formulario
                nombre = form_data.get(f"nombre_{rut}")
                
                if not nombre:
                    errores.append(f"RUT {rut}: Nombre faltante")
                    continue
                
                # Verificar que no exista ya
                cursor.execute("SELECT id FROM proveedores WHERE rut = %s", (rut,))
                if cursor.fetchone():
                    errores.append(f"RUT {rut}: Ya existe en la base de datos")
                    continue
                
                # Crear proveedor
                cursor.execute("""
                    INSERT INTO proveedores (rut, nombre, direccion, contacto, forma_pago) 
                    VALUES (%s, %s, NULL, NULL, NULL)
                """, (rut, nombre))
                
                conn.commit()
                proveedores_creados.append({"rut": rut, "nombre": nombre})
                
            except Exception as e:
                errores.append(f"RUT {rut}: Error al crear - {str(e)}")
                continue
        
        cursor.close()
        conn.close()
        
        # Preparar mensaje de resultado
        mensaje = ""
        if proveedores_creados:
            mensaje += f"✅ Se crearon {len(proveedores_creados)} proveedores correctamente. "
        if errores:
            mensaje += f"❌ Se encontraron {len(errores)} errores."
        
        return templates.TemplateResponse("finanzas/crear_proveedores.html", {
            "request": request,
            "proveedores_creados": proveedores_creados,
            "errores": errores,
            "mensaje": mensaje
        })
        
    except Exception as e:
        return templates.TemplateResponse("finanzas/crear_proveedores.html", {
            "request": request,
            "error": f"⚠️ Error al crear proveedores: {str(e)}"
        })

def formatear_pesos(valor):
    """Función para formatear montos en Python"""
    if valor is None or valor == '':
        return '$0'
    
    try:
        valor = int(float(valor))
        formatted = f"{valor:,}".replace(',', '.')
        return f"${formatted}"
    except (ValueError, TypeError):
        return '$0'

def formatear_fecha(fecha):
    """Formatea una fecha a formato DD-MM-AAAA"""
    if fecha is None:
        return ''
    
    try:
        # Si es un string, convertir a date
        if isinstance(fecha, str):
            from datetime import datetime
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        # Formatear a DD-MM-AAAA
        return fecha.strftime('%d-%m-%Y')
    except:
        return str(fecha)

@router.get("/cheques", response_class=HTMLResponse)
def listar_cheques(request: Request, cliente: Optional[str] = None, estado: Optional[str] = None, desde: Optional[str] = None, hasta: Optional[str] = None):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT p.id, c.nombre AS cliente, f.numero_documento, p.numero AS cheque, p.monto, p.estado, p.fecha
        FROM pagos_factura p
        JOIN facturas_compra f ON f.id = p.factura_id
        JOIN proveedores c ON f.proveedor_id = c.id
        WHERE p.tipo = 'cheque'
    """
    params = []

    if cliente:
        query += " AND c.nombre LIKE %s"
        params.append(f"%{cliente}%")

    if estado:
        query += " AND p.estado = %s"
        params.append(estado)

    if desde:
        query += " AND p.fecha >= %s"
        params.append(desde)

    if hasta:
        query += " AND p.fecha <= %s"
        params.append(hasta)

    query += " ORDER BY p.fecha ASC"

    cursor.execute(query, params)
    cheques = cursor.fetchall()

    cursor.close()
    conn.close()

    return templates.TemplateResponse("finanzas/cheques/index.html", {
        "request": request,
        "cheques": cheques,
    })

@router.post("/cheques/{pago_id}/actualizar-estado")
def actualizar_estado_cheque(pago_id: int, nuevo_estado: str = Form(...)):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE pagos_factura SET estado = %s WHERE id = %s", (nuevo_estado, pago_id))
        conn.commit()
        return RedirectResponse(url="/finanzas/cheques?success=estado_actualizado", status_code=303)
    except:
        conn.rollback()
        return RedirectResponse(url="/finanzas/cheques?error=fallo_actualizar", status_code=303)
    finally:
        cursor.close()
        conn.close()

@router.get("/cheques/calendario", response_class=HTMLResponse)
def ver_calendario_cheques(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT fecha, COUNT(*) AS cantidad, SUM(monto) AS total
        FROM pagos_factura
        WHERE tipo = 'cheque'
        GROUP BY fecha
        ORDER BY fecha ASC
    """)
    fechas = cursor.fetchall()

    cursor.close()
    conn.close()

    return templates.TemplateResponse("finanzas/cheques/calendario.html", {
        "request": request,
        "fechas": fechas
    })

@router.get("/cheques/detalle-fecha", response_class=HTMLResponse)
def detalle_cheques_por_fecha(request: Request, fecha: str):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.id, f.numero_documento, c.nombre AS cliente, p.numero AS cheque, p.monto, p.estado
        FROM pagos_factura p
        JOIN facturas_compra f ON f.id = p.factura_id
        JOIN proveedores c ON f.proveedor_id = c.id
        WHERE p.tipo = 'cheque' AND p.fecha = %s
        ORDER BY c.nombre
    """, (fecha,))
    cheques = cursor.fetchall()

    cursor.close()
    conn.close()

    return templates.TemplateResponse("finanzas/cheques/detalle_fecha.html", {
        "request": request,
        "cheques": cheques,
        "fecha": fecha
    })

# Agregar esta ruta al final de finanzas.py, antes del último comentario

@router.post("/cheques/{pago_id}/eliminar-con-error")
def eliminar_cheque_con_error_directo(request: Request, pago_id: int):
    """Eliminar cheque y mostrar error específico si falla"""
    
    error_info = {
        "pago_id": pago_id,
        "paso": "inicio",
        "error": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        # Paso 1: Conexión
        error_info["paso"] = "conectando_mysql"
        conn = conectar_mysql()
        
        # Paso 2: Cursor
        error_info["paso"] = "creando_cursor"
        cursor = conn.cursor(dictionary=True)
        
        # Paso 3: Verificar existencia
        error_info["paso"] = "verificando_existencia"
        cursor.execute("SELECT id, tipo, factura_id FROM pagos_factura WHERE id = %s", (pago_id,))
        cheque = cursor.fetchone()
        
        if not cheque:
            error_info["error"] = f"Cheque {pago_id} no encontrado"
            error_info["detalles"] = "El cheque no existe en la base de datos"
            cursor.close()
            conn.close()
            return mostrar_error_html(request, error_info)
        
        error_info["cheque_encontrado"] = cheque
        
        # Paso 4: Eliminación
        error_info["paso"] = "eliminando"
        cursor.execute("DELETE FROM pagos_factura WHERE id = %s", (pago_id,))
        filas_afectadas = cursor.rowcount
        error_info["filas_afectadas"] = filas_afectadas
        
        if filas_afectadas == 0:
            error_info["error"] = "No se eliminó ninguna fila"
            error_info["detalles"] = "El comando DELETE no afectó ninguna fila"
            cursor.close()
            conn.close()
            return mostrar_error_html(request, error_info)
        
        # Paso 5: Commit
        error_info["paso"] = "commit"
        conn.commit()
        
        # Paso 6: Cerrar
        cursor.close()
        conn.close()
        
        # Éxito - redirigir
        return RedirectResponse(url="/finanzas/cheques?success=eliminado_ok", status_code=303)
        
    except Exception as e:
        error_info["error"] = str(e)
        error_info["tipo_error"] = type(e).__name__
        error_info["detalles"] = f"Error en paso: {error_info['paso']}"
        
        # Detalles específicos de MySQL
        if hasattr(e, 'errno'):
            error_info["mysql_errno"] = e.errno
        if hasattr(e, 'msg'):
            error_info["mysql_msg"] = e.msg
            
        # Intentar cerrar conexiones
        try:
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        except:
            pass
            
        return mostrar_error_html(request, error_info)

def mostrar_error_html(request: Request, error_info: dict):
    """Función auxiliar para mostrar errores en HTML"""
    
    import json
    
    error_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error Eliminación Cheque</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 20px; background: #f8fafc; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ background: #dc2626; color: white; padding: 20px; border-radius: 12px 12px 0 0; }}
            .content {{ padding: 20px; }}
            .error-box {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 15px; margin: 15px 0; }}
            .info-box {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 15px; margin: 15px 0; }}
            .json-box {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; margin: 15px 0; font-family: monospace; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; margin-top: 20px; }}
            pre {{ margin: 0; white-space: pre-wrap; font-size: 14px; }}
            .step {{ color: #059669; font-weight: bold; }}
            .error-text {{ color: #dc2626; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚨 Error al Eliminar Cheque #{error_info.get('pago_id', 'N/A')}</h1>
                <p>Timestamp: {error_info.get('timestamp', 'N/A')}</p>
            </div>
            
            <div class="content">
                <div class="error-box">
                    <h3>❌ Error Principal:</h3>
                    <p class="error-text">{error_info.get('error', 'Error desconocido')}</p>
                    <p><strong>Paso donde falló:</strong> <span class="step">{error_info.get('paso', 'N/A')}</span></p>
                </div>
                
                <div class="info-box">
                    <h3>📋 Detalles de la Operación:</h3>
                    <p><strong>ID del Cheque:</strong> {error_info.get('pago_id', 'N/A')}</p>
                    <p><strong>Último paso exitoso:</strong> {error_info.get('paso', 'N/A')}</p>
                    {"<p><strong>Filas afectadas:</strong> " + str(error_info.get('filas_afectadas', 'N/A')) + "</p>" if 'filas_afectadas' in error_info else ""}
                </div>
                
                <div class="json-box">
                    <h3>🔍 Información Técnica Completa:</h3>
                    <pre>{json.dumps(error_info, indent=2, default=str, ensure_ascii=False)}</pre>
                </div>
                
                <a href="/finanzas/cheques" class="btn">← Volver a Gestión de Cheques</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=error_html, status_code=500)

@router.get("/cheques/{pago_id}/test-connection")
def test_connection(pago_id: int):
    """Probar solo la conexión y consulta básica"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Probar consulta simple
        cursor.execute("SELECT 1 as test")
        test_result = cursor.fetchone()
        
        # Probar consulta del cheque
        cursor.execute("SELECT * FROM pagos_factura WHERE id = %s", (pago_id,))
        cheque = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            "status": "success",
            "test_query": test_result,
            "cheque_found": cheque,
            "pago_id": pago_id
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "pago_id": pago_id
        }

logger = logging.getLogger(__name__)

def safe_float(value, default=0.0):
    """Convertir valor a float de forma segura"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Convertir valor a int de forma segura"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default
class CambiarEstadoRequest(BaseModel):
    numero_cheque: str
    nuevo_estado: str
    
@router.post("/cambiar-estado-cheque", response_class=JSONResponse)
def cambiar_estado_cheque(request: CambiarEstadoRequest):
    """Cambiar el estado de un cheque (solo para tabla temporal)"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Validar el nuevo estado
        if request.nuevo_estado not in ['cobrado', 'no_cobrado']:
            raise HTTPException(status_code=400, detail="Estado no válido")
        
        # Verificar que el cheque existe
        cursor.execute("""
            SELECT id, numero_cheque, estado 
            FROM cheques 
            WHERE numero_cheque = %s
        """, (request.numero_cheque,))
        
        cheque = cursor.fetchone()
        
        if not cheque:
            raise HTTPException(status_code=404, detail="Cheque no encontrado")
        
        # Actualizar el estado
        cursor.execute("""
            UPDATE cheques 
            SET estado = %s 
            WHERE numero_cheque = %s
        """, (request.nuevo_estado, request.numero_cheque))
        
        conn.commit()
        
        logger.info(f"Estado del cheque {request.numero_cheque} cambiado de {cheque['estado']} a {request.nuevo_estado}")
        
        return {
            "success": True,
            "message": f"Estado del cheque actualizado correctamente",
            "cheque": {
                "numero_cheque": request.numero_cheque,
                "estado_anterior": cheque['estado'],
                "estado_nuevo": request.nuevo_estado
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cambiando estado del cheque: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno al cambiar estado: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/cheques-por-estado", response_class=JSONResponse)
def obtener_cheques_por_estado():
    """Obtener resumen de cheques agrupados por estado"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Cheques de tabla temporal por estado
        cursor.execute("""
            SELECT 
                estado,
                COUNT(*) as cantidad,
                COALESCE(SUM(monto), 0) as monto_total
            FROM cheques
            GROUP BY estado
        """)
        
        resultados = cursor.fetchall()
        
        resumen = {
            "cobrado": {"cantidad": 0, "monto": 0},
            "no_cobrado": {"cantidad": 0, "monto": 0}
        }
        
        for resultado in resultados:
            estado = resultado["estado"]
            resumen[estado] = {
                "cantidad": safe_int(resultado["cantidad"]),
                "monto": safe_float(resultado["monto_total"])
            }
        
        # Agregar cheques del sistema (siempre cobrados)
        cursor.execute("""
            SELECT 
                COUNT(*) as cantidad,
                COALESCE(SUM(monto), 0) as monto_total
            FROM pagos_factura
            WHERE tipo = 'cheque'
        """)
        
        sistema_result = cursor.fetchone()
        if sistema_result:
            resumen["cobrado"]["cantidad"] += safe_int(sistema_result["cantidad"])
            resumen["cobrado"]["monto"] += safe_float(sistema_result["monto_total"])
        
        return {
            "success": True,
            "resumen": resumen,
            "total": {
                "cantidad": resumen["cobrado"]["cantidad"] + resumen["no_cobrado"]["cantidad"],
                "monto": resumen["cobrado"]["monto"] + resumen["no_cobrado"]["monto"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen de cheques: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener resumen: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/detalle-cheques", response_class=HTMLResponse)
def vista_detalle_cheques(request: Request):
    """Vista para el detalle de cheques de un día específico"""
    try:
        return templates.TemplateResponse("finanzas/detalle_cheques.html", {"request": request})
    except Exception as e:
        print(f"Error en vista detalle_cheques: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar la vista de detalle de cheques")