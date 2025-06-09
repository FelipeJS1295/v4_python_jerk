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
    cursor = conn.cursor()

    try:
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
        # Obtener rol del trabajador
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

        # Debug temporal - puedes quitar estas líneas después
        print(f"DEBUG: Trabajador ID: {filtro.trabajador_id}")
        print(f"DEBUG: Rol encontrado: '{rol}' (longitud: {len(rol)})")
        print(f"DEBUG: Nombre: {nombre}")

        # Determinar qué costo usar - Maneja múltiples variantes
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

        print(f"DEBUG: Campo costo determinado: {campo_costo}")

        if not campo_costo:
            # Fallback a precio_reparacion si no encuentra el rol
            campo_costo = "precio_reparacion"
            print(f"DEBUG: Usando fallback: {campo_costo}")

        # Verificar que la columna existe en productos
        cursor.execute(f"SHOW COLUMNS FROM productos LIKE '{campo_costo}'")
        columna_existe = cursor.fetchone()
        
        if not columna_existe and campo_costo != "precio_reparacion":
            print(f"DEBUG: Columna {campo_costo} no existe, usando precio_reparacion")
            campo_costo = "precio_reparacion"

        # Consulta de órdenes con manejo robusto de costos
        if campo_costo == "precio_reparacion":
            # Si usa precio_reparacion, tomarlo de la tabla produccion
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
            # Si usa costo específico, tomarlo de la tabla productos
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

        # Agregar filtros de fecha si están presentes
        if filtro.fecha_desde:
            query += " AND p.fecha >= %s"
            params.append(filtro.fecha_desde)
        if filtro.fecha_hasta:
            query += " AND p.fecha <= %s"
            params.append(filtro.fecha_hasta)

        query += " ORDER BY p.fecha DESC"
        
        print(f"DEBUG: Query final: {query}")
        print(f"DEBUG: Parámetros: {params}")
        
        cursor.execute(query, params)
        datos = cursor.fetchall()

        # Formatear fechas
        for d in datos:
            if d["fecha"]:
                d["fecha"] = d["fecha"].strftime("%Y-%m-%d")

        print(f"DEBUG: Registros encontrados: {len(datos)}")

        return {
            "trabajador": nombre,
            "rol": rol,
            "fecha_desde": filtro.fecha_desde,
            "fecha_hasta": filtro.fecha_hasta,
            "detalle": datos
        }

    except Exception as e:
        print(f"ERROR en resumen_detallado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    
    finally:
        cursor.close()
        conn.close()

@router.get("/{id}", response_class=JSONResponse)
def obtener_orden(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, t.nombres AS trabajador_nombre
        FROM produccion p
        JOIN trabajadores t ON p.trabajadores_id = t.id
        WHERE p.id = %s
    """, (id,))
    data = cursor.fetchone()

    if data and data["fecha"]:
        data["fecha"] = data["fecha"].strftime("%Y-%m-%d")

    # convertimos el nombre a objeto
    data["trabajador"] = {"nombres": data.pop("trabajador_nombre")}

    cursor.close()
    conn.close()
    return data

@router.put("/{id}", response_class=JSONResponse)
def actualizar_orden(id: int, data: ProduccionCreate):
    conn = conectar_mysql()
    cursor = conn.cursor()
    try:
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
    cursor = conn.cursor()

    try:
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

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar reparaciones: {str(e)}")

    finally:
        cursor.close()
        conn.close()

@router.get("/", response_class=HTMLResponse)
async def vista_produccion(request: Request):
    return templates.TemplateResponse("produccion.html", {"request": request})

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

@router.get("/{id}", response_class=JSONResponse)
def obtener_orden(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    # Obtener la orden principal
    cursor.execute("""
        SELECT trabajador_id, tipo
        FROM produccion
        WHERE id = %s
    """, (id,))
    orden = cursor.fetchone()
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Obtener órdenes asociadas
    if orden["tipo"] == "normal":
        cursor.execute("""
            SELECT productos_id, numero_orden_trabajo, fecha
            FROM produccion
            WHERE trabajador_id = %s AND tipo = 'normal'
        """, (orden["trabajador_id"],))
    else:
        cursor.execute("""
            SELECT producto_id, numero_orden_trabajo, fecha, descripcion, precio_reparacion
            FROM produccion
            WHERE trabajador_id = %s AND tipo = 'reparacion'
        """, (orden["trabajador_id"],))

    ordenes = cursor.fetchall()
    conn.close()

    return {
        "trabajador_id": orden["trabajador_id"],
        "tipo": orden["tipo"],
        "ordenes": ordenes
    }

@router.put("/editar/{id}", response_class=JSONResponse)
def editar_orden(id: int, data: dict):
    conn = conectar_mysql()
    cursor = conn.cursor()

    trabajador_id = data.get("trabajador_id")
    ordenes = data.get("ordenes", [])

    if not trabajador_id or not ordenes:
        raise HTTPException(status_code=400, detail="Datos incompletos")

    # Eliminar las órdenes anteriores
    cursor.execute("DELETE FROM produccion WHERE id = %s", (id,))

    # Insertar nuevas órdenes
    for orden in ordenes:
        cursor.execute("""
            INSERT INTO produccion (trabajador_id, productos_id, numero_orden_trabajo, fecha, tipo, estado)
            VALUES (%s, %s, %s, %s, 'normal', 'Pendiente')
        """, (
            trabajador_id,
            orden.get("productos_id"),
            orden.get("numero_orden_trabajo"),
            orden.get("fecha")
        ))

    conn.commit()
    conn.close()

    return {"mensaje": "Orden actualizada correctamente"}

@router.delete("/eliminar/{id}", response_class=JSONResponse)
def eliminar_orden(id: int):
    conn = conectar_mysql()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM produccion WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Orden eliminada correctamente"}