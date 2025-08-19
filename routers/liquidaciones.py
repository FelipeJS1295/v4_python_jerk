from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from db import conectar_mysql
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import logging
import pandas as pd
import io
from collections import defaultdict

# Configurar logging
logger = logging.getLogger(__name__)

# Configurar templates
templates = Jinja2Templates(directory="templates")

# Crear el router
router = APIRouter(prefix="/liquidaciones", tags=["liquidaciones"])

# Schemas para liquidaciones
class LiquidacionUpdate(BaseModel):
    numero_liquidacion: Optional[str] = None
    fecha_pago_liquidacion: Optional[str] = None
    monto_liquido: Optional[float] = None

class OrdenLiquidacion(BaseModel):
    id: int
    cliente_id: Optional[int]
    numero_orden: str
    producto: str
    estado_pago: str
    numero_liquidacion: Optional[str]
    monto_liquido: Optional[float]
    precio_cliente: Optional[float]
    fecha_compra: Optional[str]
    fecha_entrega: Optional[str]

class EstadisticasLiquidacion(BaseModel):
    total_ordenes: int
    ordenes_pagadas: int
    ordenes_pendientes: int
    ordenes_fallidas: int
    monto_total_ventas: float
    monto_total_liquidado: float
    monto_pendiente_liquidacion: float
    promedio_liquidacion: float
    clientes_unicos: int
    porcentaje_pagadas: float
    porcentaje_pendientes: float

@router.get("/", response_class=HTMLResponse)
async def mostrar_liquidaciones(request: Request):
    """
    Mostrar la página principal de gestión de liquidaciones
    """
    return templates.TemplateResponse("liquidaciones/gestion.html", {"request": request})

@router.get("/api/ventas-retail/liquidacion")
async def obtener_ordenes_liquidacion(
    search: Optional[str] = Query(None, description="Término de búsqueda"),
    numero_orden: Optional[str] = Query(None, description="Filtrar por número de orden"),
    cliente: Optional[str] = Query(None, description="Filtrar por cliente"),
    numero_liquidacion: Optional[str] = Query(None, description="Filtrar por número de liquidación"),
    estado_pago: Optional[str] = Query(None, description="Filtrar por estado de pago"),
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    limite: int = Query(100, description="Límite de resultados"),
    offset: int = Query(0, description="Offset para paginación")
):
    """
    Obtener todas las órdenes de ventas retail con información de liquidación
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Query base para obtener las órdenes con estado de pago calculado
        base_query = """
            SELECT 
                vr.cliente_id,
                vr.numero_orden,
                vr.producto,
                c.nombre as cliente_nombre,
                CASE 
                    WHEN vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NOT NULL THEN 'pagado'
                    WHEN vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NULL THEN 'pendiente'
                    ELSE 'fallido'
                END AS estado_pago,
                vr.numero_liquidacion,
                vr.monto_liquido,
                vr.precio_cliente,
                vr.fecha_compra,
                vr.fecha_entrega,
                vr.fecha_pago_liquidacion,
                vr.id
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
        """
        
        # Construir condiciones WHERE
        condiciones = []
        parametros = []
        
        # Filtro de búsqueda general
        if search and search.strip():
            condiciones.append("""
                (vr.numero_orden LIKE %s 
                OR vr.producto LIKE %s 
                OR c.nombre LIKE %s
                OR CAST(vr.cliente_id AS CHAR) LIKE %s
                OR vr.numero_liquidacion LIKE %s)
            """)
            search_param = f"%{search.strip()}%"
            parametros.extend([search_param, search_param, search_param, search_param, search_param])
        
        # Filtro específico por número de orden
        if numero_orden and numero_orden.strip():
            condiciones.append("vr.numero_orden LIKE %s")
            parametros.append(f"%{numero_orden.strip()}%")
        
        # Filtro específico por cliente
        if cliente and cliente.strip():
            condiciones.append("(c.nombre LIKE %s OR CAST(vr.cliente_id AS CHAR) LIKE %s)")
            cliente_param = f"%{cliente.strip()}%"
            parametros.extend([cliente_param, cliente_param])
        
        # Filtro específico por número de liquidación
        if numero_liquidacion and numero_liquidacion.strip():
            condiciones.append("vr.numero_liquidacion LIKE %s")
            parametros.append(f"%{numero_liquidacion.strip()}%")
        
        # Filtro por estado de pago
        if estado_pago and estado_pago in ['pendiente', 'pagado', 'fallido']:
            if estado_pago == 'pendiente':
                condiciones.append("vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NULL")
            elif estado_pago == 'pagado':
                condiciones.append("vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NOT NULL")
            elif estado_pago == 'fallido':
                condiciones.append("(vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NULL) OR (vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NOT NULL)")
        
        # Filtro por rango de fechas
        if fecha_desde:
            condiciones.append("vr.fecha_compra >= %s")
            parametros.append(fecha_desde)
        
        if fecha_hasta:
            condiciones.append("vr.fecha_compra <= %s")
            parametros.append(fecha_hasta)
        
        # Agregar condiciones WHERE si existen
        if condiciones:
            base_query += " WHERE " + " AND ".join(condiciones)
        
        # Agregar ordenamiento y paginación
        base_query += " ORDER BY vr.fecha_compra DESC, vr.id DESC"
        base_query += " LIMIT %s OFFSET %s"
        
        parametros.extend([limite, offset])
        
        # Ejecutar query
        cursor.execute(base_query, parametros)
        ordenes = cursor.fetchall()
        
        # Convertir resultados y formatear fechas
        ordenes_list = []
        for orden in ordenes:
            orden_dict = dict(orden)
            
            # Convertir tipos de datos apropiados
            if orden_dict.get('monto_liquido'):
                orden_dict['monto_liquido'] = float(orden_dict['monto_liquido'])
            if orden_dict.get('precio_cliente'):
                orden_dict['precio_cliente'] = float(orden_dict['precio_cliente'])
            if orden_dict.get('fecha_compra'):
                orden_dict['fecha_compra'] = orden_dict['fecha_compra'].isoformat() if hasattr(orden_dict['fecha_compra'], 'isoformat') else str(orden_dict['fecha_compra'])
            if orden_dict.get('fecha_entrega'):
                orden_dict['fecha_entrega'] = orden_dict['fecha_entrega'].isoformat() if hasattr(orden_dict['fecha_entrega'], 'isoformat') else str(orden_dict['fecha_entrega'])
            if orden_dict.get('fecha_pago_liquidacion'):
                orden_dict['fecha_pago_liquidacion'] = orden_dict['fecha_pago_liquidacion'].isoformat() if hasattr(orden_dict['fecha_pago_liquidacion'], 'isoformat') else str(orden_dict['fecha_pago_liquidacion'])
            
            ordenes_list.append(orden_dict)
        
        # Obtener estadísticas generales (sin filtros para mostrar totales reales)
        stats_query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN 1 ELSE 0 END) as pagados,
                SUM(CASE WHEN numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NULL THEN 1 ELSE 0 END) as pendientes,
                SUM(CASE WHEN (numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NULL) OR (numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NOT NULL) THEN 1 ELSE 0 END) as fallidos,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN monto_liquido ELSE 0 END), 0) as total_liquidado,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NULL THEN precio_cliente ELSE 0 END), 0) as total_pendiente
            FROM ventas_retail
        """
        
        cursor.execute(stats_query)
        stats = cursor.fetchone()
        
        estadisticas = {
            'total': stats['total'],
            'pagados': stats['pagados'],
            'pendientes': stats['pendientes'],
            'fallidos': stats['fallidos'],
            'total_liquidado': float(stats['total_liquidado']) if stats['total_liquidado'] else 0,
            'total_pendiente': float(stats['total_pendiente']) if stats['total_pendiente'] else 0
        }
        
        return {
            'ordenes': ordenes_list,
            'estadisticas': estadisticas,
            'total_resultados': len(ordenes_list),
            'offset': offset,
            'limite': limite
        }
        
    except Exception as e:
        logger.error(f"Error al obtener órdenes de liquidación: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/api/orden/{orden_id}")
async def obtener_detalle_orden(orden_id: int):
    """
    Obtener el detalle completo de una orden específica
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT 
                *,
                CASE 
                    WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN 'pagado'
                    WHEN numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NULL THEN 'pendiente'
                    ELSE 'fallido'
                END AS estado_pago
            FROM ventas_retail 
            WHERE id = %s
        """
        
        cursor.execute(query, (orden_id,))
        orden = cursor.fetchone()
        
        if not orden:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Convertir tipos de datos apropiados
        orden_dict = dict(orden)
        for key, value in orden_dict.items():
            if value is not None:
                if key in ['precio', 'precio_cliente', 'costo_despacho', 'monto_liquido']:
                    orden_dict[key] = float(value)
                elif key in ['fecha_compra', 'fecha_entrega', 'fecha_cliente', 'fecha_pago_liquidacion']:
                    if hasattr(value, 'isoformat'):
                        orden_dict[key] = value.isoformat()
                    else:
                        orden_dict[key] = str(value)
        
        return orden_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener detalle de orden {orden_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.put("/api/orden/{orden_id}/liquidacion")
async def actualizar_liquidacion(orden_id: int, liquidacion_data: LiquidacionUpdate):
    """
    Actualizar información de liquidación de una orden
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor()
        
        # Validar que la orden existe
        cursor.execute("SELECT id FROM ventas_retail WHERE id = %s", (orden_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Construir query de actualización
        campos_actualizacion = []
        parametros = []
        
        liquidacion_dict = liquidacion_data.dict(exclude_unset=True)
        
        if 'numero_liquidacion' in liquidacion_dict:
            campos_actualizacion.append("numero_liquidacion = %s")
            parametros.append(liquidacion_dict['numero_liquidacion'])
        
        if 'fecha_pago_liquidacion' in liquidacion_dict:
            campos_actualizacion.append("fecha_pago_liquidacion = %s")
            parametros.append(liquidacion_dict['fecha_pago_liquidacion'])
        
        if 'monto_liquido' in liquidacion_dict:
            campos_actualizacion.append("monto_liquido = %s")
            parametros.append(liquidacion_dict['monto_liquido'])
        
        if not campos_actualizacion:
            raise HTTPException(status_code=400, detail="No se proporcionaron campos para actualizar")
        
        # Agregar updated_at si existe la columna
        campos_actualizacion.append("updated_at = NOW()")
        parametros.append(orden_id)
        
        update_query = f"""
            UPDATE ventas_retail 
            SET {', '.join(campos_actualizacion)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, parametros)
        connection.commit()
        
        return {"message": "Liquidación actualizada correctamente", "orden_id": orden_id}
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error al actualizar liquidación de orden {orden_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/api/estadisticas")
async def obtener_estadisticas_liquidacion(
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)")
):
    """
    Obtener estadísticas detalladas de liquidaciones
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        condiciones = []
        parametros = []
        
        if fecha_desde:
            condiciones.append("fecha_compra >= %s")
            parametros.append(fecha_desde)
        
        if fecha_hasta:
            condiciones.append("fecha_compra <= %s")
            parametros.append(fecha_hasta)
        
        where_clause = ""
        if condiciones:
            where_clause = "WHERE " + " AND ".join(condiciones)
        
        stats_query = f"""
            SELECT 
                COUNT(*) as total_ordenes,
                SUM(CASE WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN 1 ELSE 0 END) as ordenes_pagadas,
                SUM(CASE WHEN numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NULL THEN 1 ELSE 0 END) as ordenes_pendientes,
                SUM(CASE WHEN (numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NULL) OR (numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NOT NULL) THEN 1 ELSE 0 END) as ordenes_fallidas,
                COALESCE(SUM(precio_cliente), 0) as monto_total_ventas,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN monto_liquido ELSE 0 END), 0) as monto_total_liquidado,
                COALESCE(SUM(CASE WHEN numero_liquidacion IS NULL AND fecha_pago_liquidacion IS NULL THEN precio_cliente ELSE 0 END), 0) as monto_pendiente_liquidacion,
                COALESCE(AVG(CASE WHEN numero_liquidacion IS NOT NULL AND fecha_pago_liquidacion IS NOT NULL THEN monto_liquido ELSE NULL END), 0) as promedio_liquidacion,
                COUNT(DISTINCT cliente_id) as clientes_unicos
            FROM ventas_retail 
            {where_clause}
        """
        
        cursor.execute(stats_query, parametros)
        stats = cursor.fetchone()
        
        estadisticas = {
            'total_ordenes': stats['total_ordenes'],
            'ordenes_pagadas': stats['ordenes_pagadas'],
            'ordenes_pendientes': stats['ordenes_pendientes'],
            'ordenes_fallidas': stats['ordenes_fallidas'],
            'monto_total_ventas': float(stats['monto_total_ventas']) if stats['monto_total_ventas'] else 0,
            'monto_total_liquidado': float(stats['monto_total_liquidado']) if stats['monto_total_liquidado'] else 0,
            'monto_pendiente_liquidacion': float(stats['monto_pendiente_liquidacion']) if stats['monto_pendiente_liquidacion'] else 0,
            'promedio_liquidacion': float(stats['promedio_liquidacion']) if stats['promedio_liquidacion'] else 0,
            'clientes_unicos': stats['clientes_unicos'],
            'porcentaje_pagadas': round((stats['ordenes_pagadas'] / stats['total_ordenes'] * 100) if stats['total_ordenes'] > 0 else 0, 2),
            'porcentaje_pendientes': round((stats['ordenes_pendientes'] / stats['total_ordenes'] * 100) if stats['total_ordenes'] > 0 else 0, 2)
        }
        
        return estadisticas
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/api/exportar-excel")
async def exportar_liquidaciones_excel(
    search: Optional[str] = Query(None),
    numero_orden: Optional[str] = Query(None),
    cliente: Optional[str] = Query(None),
    numero_liquidacion: Optional[str] = Query(None),
    estado_pago: Optional[str] = Query(None),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None)
):
    """
    Exportar liquidaciones a Excel
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Query similar al de obtener_ordenes_liquidacion pero sin límites
        base_query = """
            SELECT 
                vr.cliente_id,
                vr.numero_orden,
                vr.producto,
                vr.precio_cliente,
                CASE 
                    WHEN vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NOT NULL THEN 'pagado'
                    WHEN vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NULL THEN 'pendiente'
                    ELSE 'fallido'
                END AS estado_pago,
                vr.numero_liquidacion,
                vr.fecha_pago_liquidacion,
                vr.monto_liquido,
                vr.fecha_compra,
                vr.fecha_entrega,
                vr.cliente_final,
                vr.rut_documento,
                vr.telefono,
                vr.direccion,
                vr.region,
                vr.comuna
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
        """
        
        condiciones = []
        parametros = []
        
        # Aplicar filtros (mismo lógica que en obtener_ordenes_liquidacion)
        if search and search.strip():
            condiciones.append("""
                (vr.numero_orden LIKE %s 
                OR vr.producto LIKE %s 
                OR c.nombre LIKE %s
                OR CAST(vr.cliente_id AS CHAR) LIKE %s
                OR vr.numero_liquidacion LIKE %s)
            """)
            search_param = f"%{search.strip()}%"
            parametros.extend([search_param, search_param, search_param, search_param, search_param])
        
        if numero_orden and numero_orden.strip():
            condiciones.append("vr.numero_orden LIKE %s")
            parametros.append(f"%{numero_orden.strip()}%")
        
        if cliente and cliente.strip():
            condiciones.append("(c.nombre LIKE %s OR CAST(vr.cliente_id AS CHAR) LIKE %s)")
            cliente_param = f"%{cliente.strip()}%"
            parametros.extend([cliente_param, cliente_param])
        
        if numero_liquidacion and numero_liquidacion.strip():
            condiciones.append("vr.numero_liquidacion LIKE %s")
            parametros.append(f"%{numero_liquidacion.strip()}%")
        
        if estado_pago and estado_pago in ['pendiente', 'pagado', 'fallido']:
            if estado_pago == 'pendiente':
                condiciones.append("vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NULL")
            elif estado_pago == 'pagado':
                condiciones.append("vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NOT NULL")
            elif estado_pago == 'fallido':
                condiciones.append("(vr.numero_liquidacion IS NOT NULL AND vr.fecha_pago_liquidacion IS NULL) OR (vr.numero_liquidacion IS NULL AND vr.fecha_pago_liquidacion IS NOT NULL)")
        
        if fecha_desde:
            condiciones.append("vr.fecha_compra >= %s")
            parametros.append(fecha_desde)
        
        if fecha_hasta:
            condiciones.append("vr.fecha_compra <= %s")
            parametros.append(fecha_hasta)
        
        if condiciones:
            base_query += " WHERE " + " AND ".join(condiciones)
        
        base_query += " ORDER BY vr.fecha_compra DESC"
        
        cursor.execute(base_query, parametros)
        data = cursor.fetchall()
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No hay datos para exportar")
        
        # Renombrar columnas para el Excel
        column_mapping = {
            'cliente_id': 'ID Cliente',
            'numero_orden': 'Número Orden',
            'producto': 'Producto',
            'precio_cliente': 'Precio Cliente',
            'estado_pago': 'Estado Pago',
            'numero_liquidacion': 'Nº Liquidación',
            'fecha_pago_liquidacion': 'Fecha Pago',
            'monto_liquido': 'Monto Líquido',
            'fecha_compra': 'Fecha Compra',
            'fecha_entrega': 'Fecha Entrega',
            'cliente_final': 'Cliente Final',
            'rut_documento': 'RUT',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
            'region': 'Región',
            'comuna': 'Comuna'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Crear buffer para Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Liquidaciones', index=False)
        
        buffer.seek(0)
        
        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"liquidaciones_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al exportar liquidaciones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar archivo Excel: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/reportes", response_class=HTMLResponse)
async def mostrar_reportes(request: Request):
    """
    Mostrar la página de reportes de liquidaciones
    """
    return templates.TemplateResponse("liquidaciones/reportes.html", {"request": request})