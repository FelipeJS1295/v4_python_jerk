from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from db import conectar_mysql
from pydantic import BaseModel
from typing import Optional
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db import conectar_mysql
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter(prefix="/produccion", tags=["Producción"])
templates = Jinja2Templates(directory="templates")

# Vista principal de producción
@router.get("/", response_class=HTMLResponse)
async def vista_produccion(request: Request):
    return templates.TemplateResponse("produccion.html", {"request": request})

# Vista para crear nueva producción
@router.get("/create", response_class=HTMLResponse)
async def vista_crear_produccion(request: Request):
    return templates.TemplateResponse("produccion/create.html", {"request": request})

# Vista para crear nueva reparación
@router.get("/create-reparacion", response_class=HTMLResponse)
async def vista_crear_reparacion(request: Request):
    return templates.TemplateResponse("produccion/create_reparacion.html", {"request": request})

# Vista para editar producción
@router.get("/edit/{id}", response_class=HTMLResponse)
async def vista_editar_produccion(request: Request, id: int):
    return templates.TemplateResponse("produccion/edit.html", {"request": request, "orden_id": id})

@router.get("/ordenes", response_class=JSONResponse)
def obtener_ordenes_produccion():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.id,
            p.numero_orden_trabajo,
            pr.nombre AS producto,
            t.nombres AS trabajador,
            p.fecha,
            p.tipo
        FROM produccion p
        JOIN productos pr ON p.productos_id = pr.id
        JOIN trabajadores t ON p.trabajadores_id = t.id
        ORDER BY p.fecha DESC
    """)

    resultados = cursor.fetchall()
    for r in resultados:
        if r["fecha"]:
            r["fecha"] = r["fecha"].strftime("%Y-%m-%d")
        if r["tipo"] == "normal":
            r["estado"] = "Pendiente"
        elif r["tipo"] == "reparacion":
            r["estado"] = "Reparado"
        else:
            r["estado"] = "Desconocido"

    cursor.close()
    conn.close()
    return resultados

class FiltroResumen(BaseModel):
    trabajador_id: int
    fecha_desde: Optional[str] = None
    fecha_hasta: Optional[str] = None

@router.post("/resumen-trabajador", response_class=JSONResponse)
def resumen_por_trabajador(filtro: FiltroResumen):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            p.numero_orden_trabajo,
            pr.nombre AS producto,
            p.fecha,
            p.tipo,
            p.precio_reparacion,
            t.nombres AS trabajador
        FROM produccion p
        JOIN productos pr ON p.productos_id = pr.id
        JOIN trabajadores t ON p.trabajadores_id = t.id
        WHERE p.trabajadores_id = %s
    """
    params = [filtro.trabajador_id]

    if filtro.fecha_desde:
        query += " AND p.fecha >= %s"
        params.append(filtro.fecha_desde)
    if filtro.fecha_hasta:
        query += " AND p.fecha <= %s"
        params.append(filtro.fecha_hasta)

    query += " ORDER BY p.fecha DESC"

    cursor.execute(query, params)
    resultados = cursor.fetchall()

    total_unidades = len(resultados)
    total_monto = sum(r["precio_reparacion"] or 0 for r in resultados)

    for r in resultados:
        if r["fecha"]:
            r["fecha"] = r["fecha"].strftime("%Y-%m-%d")

    cursor.close()
    conn.close()

    return {
        "detalle": resultados,
        "total_unidades": total_unidades,
        "total_monto": total_monto
    }

@router.get("/trabajadores", response_class=JSONResponse)
def obtener_trabajadores():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.id, t.nombres
        FROM trabajadores t
        JOIN users u ON t.id = u.id
        WHERE u.rol IN ('Tapiceria', 'Costura', 'Esqueleteria')
    """)
    trabajadores = cursor.fetchall()
    cursor.close()
    conn.close()
    return trabajadores

class OrdenProduccion(BaseModel):
    productos_id: int
    fecha: str
    numero_orden_trabajo: str

class ProduccionBatch(BaseModel):
    trabajador_id: int
    ordenes: List[OrdenProduccion]

class ProduccionCreate(BaseModel):
    productos_id: int
    numero_orden_trabajo: str
    fecha: str

@router.post("/crear", response_class=JSONResponse)
def crear_produccion_batch(data: ProduccionBatch):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener el rol del trabajador seleccionado
        cursor.execute("""
            SELECT u.rol 
            FROM users u 
            JOIN trabajadores t ON u.id = t.id 
            WHERE t.id = %s
        """, (data.trabajador_id,))
        
        trabajador_info = cursor.fetchone()
        if not trabajador_info:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")
        
        rol_trabajador = trabajador_info["rol"]
        
        # Validar que no existan números de orden duplicados para el mismo rol
        numeros_orden = [orden.numero_orden_trabajo for orden in data.ordenes]
        
        if len(numeros_orden) != len(set(numeros_orden)):
            raise HTTPException(status_code=400, detail="No puede repetir números de orden en la misma solicitud")
        
        # Verificar números de orden existentes para el mismo rol
        placeholders = ','.join(['%s'] * len(numeros_orden))
        cursor.execute(f"""
            SELECT p.numero_orden_trabajo
            FROM produccion p
            JOIN trabajadores t ON p.trabajadores_id = t.id
            JOIN users u ON t.id = u.id
            WHERE u.rol = %s AND p.numero_orden_trabajo IN ({placeholders})
        """, [rol_trabajador] + numeros_orden)
        
        ordenes_existentes = cursor.fetchall()
        
        if ordenes_existentes:
            numeros_duplicados = [orden["numero_orden_trabajo"] for orden in ordenes_existentes]
            raise HTTPException(
                status_code=400, 
                detail=f"Los siguientes números de orden ya existen para trabajadores de {rol_trabajador}: {', '.join(numeros_duplicados)}"
            )
        
        # Si no hay duplicados, proceder con la inserción
        for orden in data.ordenes:
            cursor.execute("""
                INSERT INTO produccion (
                    trabajadores_id, productos_id, fecha, numero_orden_trabajo, tipo, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, 'normal', NOW(), NOW())
            """, (
                data.trabajador_id,
                orden.productos_id,
                orden.fecha,
                orden.numero_orden_trabajo
            ))

        conn.commit()
        return {"mensaje": "Producción registrada correctamente"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar producción: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@router.post("/resumen-detallado", response_class=JSONResponse)
def resumen_detallado_trabajador(filtro: FiltroResumen):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT u.rol, t.nombres 
            FROM users u 
            JOIN trabajadores t ON u.id = t.id 
            WHERE t.id = %s
        """, (filtro.trabajador_id,))
        
        user_data = cursor.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")

        rol = user_data["rol"].strip() if user_data["rol"] else ""
        nombre = user_data["nombres"]

        campo_costo = {
            "Tapiceria": "costo_tapiceria",
            "Tapicería": "costo_tapiceria", 
            "tapiceria": "costo_tapiceria",
            "TAPICERIA": "costo_tapiceria",
            "Costura": "costo_costura",
            "costura": "costo_costura", 
            "COSTURA": "costo_costura",
            "Esqueleteria": "costo_esqueleteria",
            "esqueleteria": "costo_esqueleteria",
            "ESQUELETERIA": "costo_esqueleteria"
        }.get(rol, None)

        if not campo_costo:
            campo_costo = "precio_reparacion"

        cursor.execute(f"SHOW COLUMNS FROM productos LIKE '{campo_costo}'")
        columna_existe = cursor.fetchone()
        
        if not columna_existe and campo_costo != "precio_reparacion":
            campo_costo = "precio_reparacion"

        if campo_costo == "precio_reparacion":
            query = """
                SELECT 
                    p.fecha,
                    p.numero_orden_trabajo,
                    pr.nombre AS producto,
                    p.tipo,
                    p.descripcion,
                    COALESCE(p.precio_reparacion, 0) AS costo
                FROM produccion p
                JOIN productos pr ON p.productos_id = pr.id
                WHERE p.trabajadores_id = %s
            """
        else:
            query = f"""
                SELECT 
                    p.fecha,
                    p.numero_orden_trabajo,
                    pr.nombre AS producto,
                    p.tipo,
                    p.descripcion,
                    COALESCE(pr.{campo_costo}, p.precio_reparacion, 0) AS costo
                FROM produccion p
                JOIN productos pr ON p.productos_id = pr.id
                WHERE p.trabajadores_id = %s
            """
        
        params = [filtro.trabajador_id]

        if filtro.fecha_desde:
            query += " AND p.fecha >= %s"
            params.append(filtro.fecha_desde)
        if filtro.fecha_hasta:
            query += " AND p.fecha <= %s"
            params.append(filtro.fecha_hasta)

        query += " ORDER BY p.fecha DESC"
        
        cursor.execute(query, params)
        datos = cursor.fetchall()

        for d in datos:
            if d["fecha"]:
                d["fecha"] = d["fecha"].strftime("%Y-%m-%d")

        return {
            "trabajador": nombre,
            "rol": rol,
            "fecha_desde": filtro.fecha_desde,
            "fecha_hasta": filtro.fecha_hasta,
            "detalle": datos
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
    finally:
        cursor.close()
        conn.close()

@router.get("/orden/{id}", response_class=JSONResponse)
def obtener_orden(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, t.nombres AS trabajador_nombre, pr.nombre AS producto_nombre
        FROM produccion p
        JOIN trabajadores t ON p.trabajadores_id = t.id
        JOIN productos pr ON p.productos_id = pr.id
        WHERE p.id = %s
    """, (id,))
    data = cursor.fetchone()

    if not data:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if data and data["fecha"]:
        data["fecha"] = data["fecha"].strftime("%Y-%m-%d")

    cursor.close()
    conn.close()
    return data

@router.put("/{id}", response_class=JSONResponse)
def actualizar_orden(id: int, data: ProduccionCreate):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        # Obtener información actual de la orden
        cursor.execute("""
            SELECT p.numero_orden_trabajo, p.trabajadores_id, u.rol
            FROM produccion p
            JOIN trabajadores t ON p.trabajadores_id = t.id
            JOIN users u ON t.id = u.id
            WHERE p.id = %s
        """, (id,))
        
        orden_actual = cursor.fetchone()
        if not orden_actual:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Solo validar si el número de orden cambió
        if orden_actual["numero_orden_trabajo"] != data.numero_orden_trabajo:
            rol_trabajador = orden_actual["rol"]
            
            # Verificar si el nuevo número de orden ya existe para el mismo rol
            cursor.execute("""
                SELECT p.id
                FROM produccion p
                JOIN trabajadores t ON p.trabajadores_id = t.id
                JOIN users u ON t.id = u.id
                WHERE u.rol = %s AND p.numero_orden_trabajo = %s AND p.id != %s
            """, (rol_trabajador, data.numero_orden_trabajo, id))
            
            orden_existente = cursor.fetchone()
            if orden_existente:
                raise HTTPException(
                    status_code=400, 
                    detail=f"El número de orden {data.numero_orden_trabajo} ya existe para otro trabajador de {rol_trabajador}"
                )
        
        # Actualizar la orden
        cursor.execute("""
            UPDATE produccion
            SET productos_id = %s, numero_orden_trabajo = %s, fecha = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            data.productos_id,
            data.numero_orden_trabajo,
            data.fecha,
            id
        ))
        conn.commit()
        return {"mensaje": "Producción actualizada correctamente"}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

class OrdenReparacionItem(BaseModel):
    producto_id: int
    fecha: str
    numero_orden_trabajo: str
    descripcion: Optional[str] = None
    precio_reparacion: Optional[float] = 0

class ReparacionCreate(BaseModel):
    trabajadores_id: int
    ordenes: List[OrdenReparacionItem]

@router.post("/crear-reparacion", response_class=JSONResponse)
def crear_reparaciones(data: ReparacionCreate):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    try:
        # Obtener el rol del trabajador seleccionado
        cursor.execute("""
            SELECT u.rol 
            FROM users u 
            JOIN trabajadores t ON u.id = t.id 
            WHERE t.id = %s
        """, (data.trabajadores_id,))
        
        trabajador_info = cursor.fetchone()
        if not trabajador_info:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")
        
        rol_trabajador = trabajador_info["rol"]
        
        # Validar que no existan números de orden duplicados para el mismo rol
        numeros_orden = [orden.numero_orden_trabajo for orden in data.ordenes]
        
        if len(numeros_orden) != len(set(numeros_orden)):
            raise HTTPException(status_code=400, detail="No puede repetir números de orden en la misma solicitud")
        
        # Verificar números de orden existentes para el mismo rol
        placeholders = ','.join(['%s'] * len(numeros_orden))
        cursor.execute(f"""
            SELECT p.numero_orden_trabajo
            FROM produccion p
            JOIN trabajadores t ON p.trabajadores_id = t.id
            JOIN users u ON t.id = u.id
            WHERE u.rol = %s AND p.numero_orden_trabajo IN ({placeholders})
        """, [rol_trabajador] + numeros_orden)
        
        ordenes_existentes = cursor.fetchall()
        
        if ordenes_existentes:
            numeros_duplicados = [orden["numero_orden_trabajo"] for orden in ordenes_existentes]
            raise HTTPException(
                status_code=400, 
                detail=f"Los siguientes números de orden ya existen para trabajadores de {rol_trabajador}: {', '.join(numeros_duplicados)}"
            )
        
        # Si no hay duplicados, proceder con la inserción
        for orden in data.ordenes:
            cursor.execute("""
                INSERT INTO produccion (
                    trabajadores_id, productos_id, fecha, numero_orden_trabajo, descripcion, precio_reparacion,
                    tipo, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'reparacion', NOW(), NOW())
            """, (
                data.trabajadores_id,
                orden.producto_id,
                orden.fecha,
                orden.numero_orden_trabajo,
                orden.descripcion,
                orden.precio_reparacion
            ))

        conn.commit()
        return {"mensaje": "Reparaciones registradas correctamente"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar reparaciones: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@router.get("/productos/")
async def obtener_productos():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, nombre, sku FROM productos ORDER BY nombre")
        productos = cursor.fetchall()
        return productos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.delete("/eliminar/{id}", response_class=JSONResponse)
def eliminar_orden(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM produccion WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    return {"mensaje": "Orden eliminada correctamente"}

@router.post("/validar-numero-orden", response_class=JSONResponse)
def validar_numero_orden(data: dict):
    """Validar si un número de orden ya existe para un trabajador del mismo rol"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        trabajador_id = data.get("trabajador_id")
        numero_orden = data.get("numero_orden_trabajo")
        orden_id = data.get("orden_id", None)  # Para edición
        
        if not trabajador_id or not numero_orden:
            return {"valido": False, "mensaje": "Datos incompletos"}
        
        # Obtener el rol del trabajador
        cursor.execute("""
            SELECT u.rol 
            FROM users u 
            JOIN trabajadores t ON u.id = t.id 
            WHERE t.id = %s
        """, (trabajador_id,))
        
        trabajador_info = cursor.fetchone()
        if not trabajador_info:
            return {"valido": False, "mensaje": "Trabajador no encontrado"}
        
        rol_trabajador = trabajador_info["rol"]
        
        # Verificar si el número de orden ya existe para el mismo rol
        if orden_id:  # Para edición - excluir la orden actual
            cursor.execute("""
                SELECT p.numero_orden_trabajo, t.nombres
                FROM produccion p
                JOIN trabajadores t ON p.trabajadores_id = t.id
                JOIN users u ON t.id = u.id
                WHERE u.rol = %s AND p.numero_orden_trabajo = %s AND p.id != %s
                LIMIT 1
            """, (rol_trabajador, numero_orden, orden_id))
        else:  # Para creación nueva
            cursor.execute("""
                SELECT p.numero_orden_trabajo, t.nombres
                FROM produccion p
                JOIN trabajadores t ON p.trabajadores_id = t.id
                JOIN users u ON t.id = u.id
                WHERE u.rol = %s AND p.numero_orden_trabajo = %s
                LIMIT 1
            """, (rol_trabajador, numero_orden))
        
        orden_existente = cursor.fetchone()
        
        if orden_existente:
            return {
                "valido": False, 
                "mensaje": f"El número de orden '{numero_orden}' ya está asignado a {orden_existente['nombres']} ({rol_trabajador})"
            }
        
        return {"valido": True, "mensaje": "Número de orden disponible"}
        
    except Exception as e:
        return {"valido": False, "mensaje": f"Error al validar: {str(e)}"}
    
    finally:
        cursor.close()
        conn.close()

@router.get("/precios/{tipo}")
def obtener_precios(tipo: str):
    tipo_campo = {
        "costura": "costo_costura",
        "tapiceria": "costo_tapiceria",
        "esqueleteria": "costo_esqueleteria"
    }

    if tipo not in tipo_campo:
        return JSONResponse(content=[], status_code=400)

    campo = tipo_campo[tipo]
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT nombre, {campo} as costo
        FROM productos
        WHERE {campo} IS NOT NULL AND {campo} > 0
        ORDER BY nombre
    """)
    resultados = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultados