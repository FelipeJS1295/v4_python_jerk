from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from db import conectar_mysql
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging
import pandas as pd
import io

# Configurar logging
logger = logging.getLogger(__name__)

# Configurar templates
templates = Jinja2Templates(directory="templates")

# Crear el router
router = APIRouter(prefix="/liquidaciones/resumen", tags=["resumen_liquidaciones"])

# Schema para resumen de liquidaciones
class ResumenLiquidacion(BaseModel):
    cliente_id: Optional[int]
    cliente_nombre: Optional[str]
    fecha_pago_liquidacion: Optional[str]
    numero_liquidacion: Optional[str]
    total_ordenes: int
    total_liquidacion: float

@router.get("/", response_class=HTMLResponse)
async def mostrar_resumen_liquidaciones(request: Request):
    """
    Mostrar la página de resumen de liquidaciones
    """
    return templates.TemplateResponse("liquidaciones/resumen_liquidaciones.html", {"request": request})

@router.get("/api/datos")
async def obtener_resumen_liquidaciones(
    search: Optional[str] = Query(None, description="Término de búsqueda"),
    cliente_id: Optional[int] = Query(None, description="Filtrar por cliente"),
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    limite: int = Query(100, description="Límite de resultados"),
    offset: int = Query(0, description="Offset para paginación")
):
    """
    Obtener resumen de liquidaciones agrupadas
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Query para obtener resumen de liquidaciones
        base_query = """
            SELECT 
                vr.cliente_id,
                c.nombre as cliente_nombre,
                vr.fecha_pago_liquidacion,
                vr.numero_liquidacion,
                COUNT(vr.id) as total_ordenes,
                COALESCE(SUM(vr.monto_liquido), 0) as total_liquidacion
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.numero_liquidacion IS NOT NULL 
            AND vr.fecha_pago_liquidacion IS NOT NULL
        """
        
        # Construir condiciones WHERE adicionales
        condiciones = []
        parametros = []
        
        # Filtro de búsqueda
        if search and search.strip():
            condiciones.append("""
                (vr.numero_liquidacion LIKE %s 
                OR c.nombre LIKE %s
                OR CAST(vr.cliente_id AS CHAR) LIKE %s)
            """)
            search_param = f"%{search.strip()}%"
            parametros.extend([search_param, search_param, search_param])
        
        # Filtro por cliente
        if cliente_id:
            condiciones.append("vr.cliente_id = %s")
            parametros.append(cliente_id)
        
        # Filtro por fecha desde
        if fecha_desde:
            condiciones.append("vr.fecha_pago_liquidacion >= %s")
            parametros.append(fecha_desde)
        
        # Filtro por fecha hasta
        if fecha_hasta:
            condiciones.append("vr.fecha_pago_liquidacion <= %s")
            parametros.append(fecha_hasta)
        
        # Agregar condiciones WHERE adicionales si existen
        if condiciones:
            base_query += " AND " + " AND ".join(condiciones)
        
        # Agregar GROUP BY y ordenamiento
        base_query += """
            GROUP BY vr.cliente_id, vr.numero_liquidacion, vr.fecha_pago_liquidacion
            ORDER BY vr.fecha_pago_liquidacion DESC, vr.numero_liquidacion DESC
        """
        
        # Agregar paginación
        base_query += " LIMIT %s OFFSET %s"
        parametros.extend([limite, offset])
        
        # Ejecutar query
        cursor.execute(base_query, parametros)
        liquidaciones = cursor.fetchall()
        
        # Convertir resultados y formatear datos
        liquidaciones_list = []
        for liquidacion in liquidaciones:
            liquidacion_dict = dict(liquidacion)
            
            # Convertir tipos de datos apropiados
            if liquidacion_dict.get('total_liquidacion'):
                liquidacion_dict['total_liquidacion'] = float(liquidacion_dict['total_liquidacion'])
            if liquidacion_dict.get('fecha_pago_liquidacion'):
                liquidacion_dict['fecha_pago_liquidacion'] = liquidacion_dict['fecha_pago_liquidacion'].isoformat() if hasattr(liquidacion_dict['fecha_pago_liquidacion'], 'isoformat') else str(liquidacion_dict['fecha_pago_liquidacion'])
            
            liquidaciones_list.append(liquidacion_dict)
        
        # Obtener estadísticas generales
        stats_query = """
            SELECT 
                COUNT(DISTINCT vr.numero_liquidacion) as total_liquidaciones,
                COUNT(vr.id) as total_ordenes_liquidadas,
                COALESCE(SUM(vr.monto_liquido), 0) as monto_total_liquidado,
                COUNT(DISTINCT vr.cliente_id) as clientes_diferentes
            FROM ventas_retail vr
            WHERE vr.numero_liquidacion IS NOT NULL 
            AND vr.fecha_pago_liquidacion IS NOT NULL
        """
        
        # Aplicar los mismos filtros a las estadísticas
        if condiciones:
            stats_query_params = []
            stats_conditions = []
            
            if search and search.strip():
                stats_conditions.append("""
                    (vr.numero_liquidacion LIKE %s 
                    OR EXISTS(SELECT 1 FROM clientes c WHERE c.id = vr.cliente_id AND c.nombre LIKE %s)
                    OR CAST(vr.cliente_id AS CHAR) LIKE %s)
                """)
                stats_query_params.extend([search_param, search_param, search_param])
            
            if cliente_id:
                stats_conditions.append("vr.cliente_id = %s")
                stats_query_params.append(cliente_id)
                
            if fecha_desde:
                stats_conditions.append("vr.fecha_pago_liquidacion >= %s")
                stats_query_params.append(fecha_desde)
                
            if fecha_hasta:
                stats_conditions.append("vr.fecha_pago_liquidacion <= %s")
                stats_query_params.append(fecha_hasta)
            
            if stats_conditions:
                stats_query += " AND " + " AND ".join(stats_conditions)
                cursor.execute(stats_query, stats_query_params)
            else:
                cursor.execute(stats_query)
        else:
            cursor.execute(stats_query)
        
        stats = cursor.fetchone()
        
        estadisticas = {
            'total_liquidaciones': stats['total_liquidaciones'],
            'total_ordenes_liquidadas': stats['total_ordenes_liquidadas'],
            'monto_total_liquidado': float(stats['monto_total_liquidado']) if stats['monto_total_liquidado'] else 0,
            'clientes_diferentes': stats['clientes_diferentes']
        }
        
        return {
            'liquidaciones': liquidaciones_list,
            'estadisticas': estadisticas,
            'total_resultados': len(liquidaciones_list),
            'offset': offset,
            'limite': limite
        }
        
    except Exception as e:
        logger.error(f"Error al obtener resumen de liquidaciones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/api/detalle/{numero_liquidacion}")
async def obtener_detalle_liquidacion(numero_liquidacion: str):
    """
    Obtener detalle de órdenes por número de liquidación
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT 
                vr.id,
                vr.numero_orden,
                vr.producto,
                vr.precio_cliente,
                vr.monto_liquido,
                vr.fecha_compra,
                vr.cliente_final,
                c.nombre as cliente_nombre
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.numero_liquidacion = %s
            ORDER BY vr.fecha_compra DESC
        """
        
        cursor.execute(query, (numero_liquidacion,))
        ordenes = cursor.fetchall()
        
        if not ordenes:
            raise HTTPException(status_code=404, detail="No se encontraron órdenes para esta liquidación")
        
        # Convertir tipos de datos apropiados
        ordenes_list = []
        for orden in ordenes:
            orden_dict = dict(orden)
            if orden_dict.get('precio_cliente'):
                orden_dict['precio_cliente'] = float(orden_dict['precio_cliente'])
            if orden_dict.get('monto_liquido'):
                orden_dict['monto_liquido'] = float(orden_dict['monto_liquido'])
            if orden_dict.get('fecha_compra'):
                orden_dict['fecha_compra'] = orden_dict['fecha_compra'].isoformat() if hasattr(orden_dict['fecha_compra'], 'isoformat') else str(orden_dict['fecha_compra'])
            
            ordenes_list.append(orden_dict)
        
        return {
            'numero_liquidacion': numero_liquidacion,
            'ordenes': ordenes_list,
            'total_ordenes': len(ordenes_list),
            'total_monto': sum(float(orden.get('monto_liquido', 0)) for orden in ordenes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener detalle de liquidación {numero_liquidacion}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
    
    finally:
        if connection:
            connection.close()

@router.get("/api/exportar")
async def exportar_resumen_liquidaciones(
    search: Optional[str] = Query(None),
    cliente_id: Optional[int] = Query(None),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None)
):
    """
    Exportar resumen de liquidaciones a Excel
    """
    connection = None
    try:
        connection = conectar_mysql()
        cursor = connection.cursor(dictionary=True)
        
        # Query similar al de obtener_resumen_liquidaciones pero sin límites
        base_query = """
            SELECT 
                vr.cliente_id,
                c.nombre as cliente_nombre,
                vr.fecha_pago_liquidacion,
                vr.numero_liquidacion,
                COUNT(vr.id) as total_ordenes,
                COALESCE(SUM(vr.monto_liquido), 0) as total_liquidacion
            FROM ventas_retail vr
            LEFT JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.numero_liquidacion IS NOT NULL 
            AND vr.fecha_pago_liquidacion IS NOT NULL
        """
        
        condiciones = []
        parametros = []
        
        # Aplicar filtros
        if search and search.strip():
            condiciones.append("""
                (vr.numero_liquidacion LIKE %s 
                OR c.nombre LIKE %s
                OR CAST(vr.cliente_id AS CHAR) LIKE %s)
            """)
            search_param = f"%{search.strip()}%"
            parametros.extend([search_param, search_param, search_param])
        
        if cliente_id:
            condiciones.append("vr.cliente_id = %s")
            parametros.append(cliente_id)
        
        if fecha_desde:
            condiciones.append("vr.fecha_pago_liquidacion >= %s")
            parametros.append(fecha_desde)
        
        if fecha_hasta:
            condiciones.append("vr.fecha_pago_liquidacion <= %s")
            parametros.append(fecha_hasta)
        
        if condiciones:
            base_query += " AND " + " AND ".join(condiciones)
        
        base_query += """
            GROUP BY vr.cliente_id, vr.numero_liquidacion, vr.fecha_pago_liquidacion
            ORDER BY vr.fecha_pago_liquidacion DESC
        """
        
        cursor.execute(base_query, parametros)
        data = cursor.fetchall()
        
        if not data:
            raise HTTPException(status_code=404, detail="No hay datos para exportar")
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        # Renombrar columnas para el Excel
        column_mapping = {
            'cliente_id': 'ID Cliente',
            'cliente_nombre': 'Cliente',
            'fecha_pago_liquidacion': 'Fecha Pago',
            'numero_liquidacion': 'Nº Liquidación',
            'total_ordenes': 'Total Órdenes',
            'total_liquidacion': 'Total Liquidación'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Crear buffer para Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Resumen Liquidaciones', index=False)
        
        buffer.seek(0)
        
        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resumen_liquidaciones_{timestamp}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(buffer.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al exportar resumen de liquidaciones: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar archivo Excel: {str(e)}")
    
    finally:
        if connection:
            connection.close()