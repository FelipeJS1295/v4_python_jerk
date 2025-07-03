from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
from datetime import datetime, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")

class Periodo(BaseModel):
    desde: str  # formato "YYYY-MM-DD"
    hasta: str

class ComparacionRequest(BaseModel):
    periodo_a: Periodo
    periodo_b: Periodo

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

@router.get("/", response_class=HTMLResponse)
def vista_dashboard(request: Request):
    """Vista principal del dashboard"""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        logger.error(f"Error en vista dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar la vista del dashboard")

@router.get("/kpis", response_class=JSONResponse)
def obtener_kpis(fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None):
    """Obtener KPIs principales del dashboard con filtros de fecha"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Construir filtros de fecha
        filtros = []
        params = []
        
        if fecha_desde:
            filtros.append("v.fecha_compra >= %s")
            params.append(fecha_desde)
        if fecha_hasta:
            filtros.append("v.fecha_compra <= %s")
            params.append(fecha_hasta)
            
        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

        # Query para obtener totales de ventas
        query_totales = f"""
            SELECT 
                COUNT(*) as total_ordenes,
                COALESCE(SUM(v.precio), 0) as total_ventas,
                COALESCE(SUM(v.unidades), 0) as total_unidades,
                COALESCE(SUM(
                    v.precio - 
                    COALESCE(v.costo_despacho, 0) - 
                    (v.precio * 0.19) - 
                    (v.precio * COALESCE(c.porcentaje_comision, 0) / 100)
                ), 0) as margen_neto
            FROM ventas_retail v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            {where_clause}
        """
        
        logger.info(f"Ejecutando query KPIs: {query_totales} con parámetros: {params}")
        
        cursor.execute(query_totales, params)
        totales = cursor.fetchone()

        # Facturas pendientes (sin filtro de fecha)
        cursor.execute("""
            SELECT COUNT(*) as facturas_pendientes
            FROM facturas_compra
            WHERE estado = 'pendiente'
        """)
        facturas_result = cursor.fetchone()

        # Validar y convertir resultados
        resultado = {
            "total_ventas": safe_float(totales["total_ventas"]),
            "total_unidades": safe_int(totales["total_unidades"]),
            "total_ordenes": safe_int(totales["total_ordenes"]),
            "margen_neto": safe_float(totales["margen_neto"]),
            "facturas_pendientes": safe_int(facturas_result["facturas_pendientes"] if facturas_result else 0)
        }
        
        logger.info(f"KPIs calculados: {resultado}")
        return resultado

    except Exception as e:
        logger.error(f"Error en /kpis: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno en el cálculo de KPIs: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/ventas-tendencia", response_class=JSONResponse)
def obtener_tendencia_ventas(dias: int = 30):
    """Obtener tendencia de ventas por día"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Calcular fecha de inicio
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=dias)

        query = """
            SELECT 
                DATE(v.fecha_compra) as fecha,
                COALESCE(SUM(v.precio), 0) as total_dia,
                COUNT(*) as ordenes_dia
            FROM ventas_retail v
            WHERE v.fecha_compra >= %s AND v.fecha_compra <= %s
            GROUP BY DATE(v.fecha_compra)
            ORDER BY fecha ASC
        """
        
        cursor.execute(query, (fecha_inicio.date(), fecha_fin.date()))
        resultados = cursor.fetchall()

        # Formatear datos para el gráfico
        fechas = []
        ventas = []
        ordenes = []

        for row in resultados:
            fechas.append(row["fecha"].strftime("%d/%m"))
            ventas.append(safe_float(row["total_dia"]))
            ordenes.append(safe_int(row["ordenes_dia"]))

        return {
            "fechas": fechas,
            "ventas": ventas,
            "ordenes": ordenes
        }

    except Exception as e:
        logger.error(f"Error en /ventas-tendencia: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener tendencia de ventas: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/top-clientes", response_class=JSONResponse)
def obtener_top_clientes(limite: int = 5, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None):
    """Obtener top clientes por volumen de ventas"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Construir filtros de fecha
        filtros = []
        params = []
        
        if fecha_desde:
            filtros.append("v.fecha_compra >= %s")
            params.append(fecha_desde)
        if fecha_hasta:
            filtros.append("v.fecha_compra <= %s")
            params.append(fecha_hasta)
            
        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""
        params.append(limite)

        query = f"""
            SELECT 
                COALESCE(c.nombre, 'Cliente Desconocido') as nombre,
                COALESCE(SUM(v.precio), 0) as total_ventas,
                COUNT(*) as total_ordenes
            FROM ventas_retail v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            {where_clause}
            GROUP BY c.id, c.nombre
            HAVING total_ventas > 0
            ORDER BY total_ventas DESC
            LIMIT %s
        """
        
        logger.info(f"Query top clientes: {query} con parámetros: {params}")
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()

        clientes = []
        for row in resultados:
            clientes.append({
                "nombre": row["nombre"] or "Cliente Desconocido",
                "total_ventas": safe_float(row["total_ventas"]),
                "total_ordenes": safe_int(row["total_ordenes"])
            })

        return {"clientes": clientes}

    except Exception as e:
        logger.error(f"Error en /top-clientes: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener top clientes: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/productos-mensuales", response_class=JSONResponse)
def obtener_productos_mensuales(fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None, limite: int = 5):
    """Obtener productos más vendidos agrupados por mes"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Construir filtros de fecha
        filtros = ["v.producto IS NOT NULL", "v.producto != ''", "TRIM(v.producto) != ''"]
        params = []
        
        if fecha_desde:
            filtros.append("v.fecha_compra >= %s")
            params.append(fecha_desde)
        if fecha_hasta:
            filtros.append("v.fecha_compra <= %s")
            params.append(fecha_hasta)
            
        where_clause = "WHERE " + " AND ".join(filtros)

        query = f"""
            SELECT 
                DATE_FORMAT(v.fecha_compra, '%Y-%m') as mes,
                TRIM(v.producto) as producto,
                COALESCE(SUM(v.unidades), 0) as total_unidades,
                COALESCE(SUM(v.precio), 0) as total_ventas,
                COUNT(*) as total_ordenes
            FROM ventas_retail v
            {where_clause}
            GROUP BY DATE_FORMAT(v.fecha_compra, '%Y-%m'), TRIM(v.producto)
            HAVING total_unidades > 0
            ORDER BY mes DESC, total_unidades DESC
        """
        
        logger.info(f"Query productos mensuales: {query} con parámetros: {params}")
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()

        # Organizar datos por mes
        datos_por_mes = {}
        for row in resultados:
            mes = row["mes"]
            if mes not in datos_por_mes:
                datos_por_mes[mes] = []
            
            if len(datos_por_mes[mes]) < limite:
                datos_por_mes[mes].append({
                    "producto": row["producto"],
                    "total_unidades": safe_int(row["total_unidades"]),
                    "total_ventas": safe_float(row["total_ventas"]),
                    "total_ordenes": safe_int(row["total_ordenes"])
                })

        return {"datos_por_mes": datos_por_mes}

    except Exception as e:
        logger.error(f"Error en /productos-mensuales: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener productos mensuales: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/calendario-cheques", response_class=JSONResponse)
def obtener_calendario_cheques(año: Optional[int] = None, mes: Optional[int] = None):
    """Obtener calendario de cheques combinando pagos_factura y tabla cheques"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Si no se especifica año/mes, usar actual
        if not año or not mes:
            hoy = datetime.now()
            año = año or hoy.year
            mes = mes or hoy.month

        # Verificar que las tablas existan antes de hacer la consulta
        cursor.execute("SHOW TABLES LIKE 'pagos_factura'")
        tabla_pagos_existe = cursor.fetchone() is not None
        
        cursor.execute("SHOW TABLES LIKE 'cheques'")
        tabla_cheques_existe = cursor.fetchone() is not None

        dias_con_cheques = {}

        # Query para pagos_factura si existe
        if tabla_pagos_existe:
            try:
                query_sistema = """
                    SELECT 
                        DAY(pf.fecha) as dia,
                        COUNT(*) as cantidad_cheques,
                        COALESCE(SUM(pf.monto), 0) as monto_total
                    FROM pagos_factura pf
                    WHERE pf.tipo = 'cheque' 
                    AND YEAR(pf.fecha) = %s 
                    AND MONTH(pf.fecha) = %s
                    GROUP BY DAY(pf.fecha)
                """
                
                cursor.execute(query_sistema, (año, mes))
                resultados_sistema = cursor.fetchall()
                
                for resultado in resultados_sistema:
                    dia = resultado["dia"]
                    if dia not in dias_con_cheques:
                        dias_con_cheques[dia] = {
                            "cantidad": 0,
                            "monto": 0,
                            "detalles": {
                                "sistema": {"cantidad": 0, "monto": 0},
                                "temporal": {"cantidad": 0, "monto": 0}
                            }
                        }
                    
                    cantidad = safe_int(resultado["cantidad_cheques"])
                    monto = safe_float(resultado["monto_total"])
                    
                    dias_con_cheques[dia]["cantidad"] += cantidad
                    dias_con_cheques[dia]["monto"] += monto
                    dias_con_cheques[dia]["detalles"]["sistema"]["cantidad"] = cantidad
                    dias_con_cheques[dia]["detalles"]["sistema"]["monto"] = monto
                    
            except Exception as e:
                logger.warning(f"Error consultando pagos_factura: {e}")

        # Query para tabla cheques si existe
        if tabla_cheques_existe:
            try:
                query_temporal = """
                    SELECT 
                        DAY(c.fecha_cheque) as dia,
                        COUNT(*) as cantidad_cheques,
                        COALESCE(SUM(c.monto), 0) as monto_total
                    FROM cheques c
                    WHERE YEAR(c.fecha_cheque) = %s 
                    AND MONTH(c.fecha_cheque) = %s
                    GROUP BY DAY(c.fecha_cheque)
                """
                
                cursor.execute(query_temporal, (año, mes))
                resultados_temporal = cursor.fetchall()
                
                for resultado in resultados_temporal:
                    dia = resultado["dia"]
                    if dia not in dias_con_cheques:
                        dias_con_cheques[dia] = {
                            "cantidad": 0,
                            "monto": 0,
                            "detalles": {
                                "sistema": {"cantidad": 0, "monto": 0},
                                "temporal": {"cantidad": 0, "monto": 0}
                            }
                        }
                    
                    cantidad = safe_int(resultado["cantidad_cheques"])
                    monto = safe_float(resultado["monto_total"])
                    
                    dias_con_cheques[dia]["cantidad"] += cantidad
                    dias_con_cheques[dia]["monto"] += monto
                    dias_con_cheques[dia]["detalles"]["temporal"]["cantidad"] = cantidad
                    dias_con_cheques[dia]["detalles"]["temporal"]["monto"] = monto
                    
            except Exception as e:
                logger.warning(f"Error consultando tabla cheques: {e}")

        # Redondear montos
        for dia in dias_con_cheques:
            dias_con_cheques[dia]["monto"] = round(dias_con_cheques[dia]["monto"], 2)
            dias_con_cheques[dia]["detalles"]["sistema"]["monto"] = round(
                dias_con_cheques[dia]["detalles"]["sistema"]["monto"], 2
            )
            dias_con_cheques[dia]["detalles"]["temporal"]["monto"] = round(
                dias_con_cheques[dia]["detalles"]["temporal"]["monto"], 2
            )

        return {
            "año": año,
            "mes": mes,
            "dias_con_cheques": dias_con_cheques
        }

    except Exception as e:
        logger.error(f"Error en /calendario-cheques: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener calendario de cheques: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/calendario-cheques/detalle", response_class=JSONResponse)
def obtener_detalle_dia_cheques(año: int, mes: int, dia: int):
    """Obtener detalle de cheques para un día específico"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        fecha_especifica = f"{año}-{mes:02d}-{dia:02d}"
        todos_cheques = []
        
        # Verificar que las tablas existan
        cursor.execute("SHOW TABLES LIKE 'pagos_factura'")
        if cursor.fetchone():
            try:
                cursor.execute("""
                    SELECT 
                        COALESCE(pf.numero, 'N/A') as numero_cheque,
                        COALESCE(pf.monto, 0) as monto,
                        COALESCE(p.nombre, 'Proveedor Desconocido') as proveedor,
                        COALESCE(pf.estado, 'N/A') as estado,
                        'Sistema Actual' as origen
                    FROM pagos_factura pf
                    LEFT JOIN facturas_compra f ON f.id = pf.factura_id
                    LEFT JOIN proveedores p ON f.proveedor_id = p.id
                    WHERE pf.tipo = 'cheque' 
                    AND DATE(pf.fecha) = %s
                    ORDER BY pf.numero
                """, (fecha_especifica,))
                
                cheques_sistema = cursor.fetchall()
                todos_cheques.extend(cheques_sistema)
                
            except Exception as e:
                logger.warning(f"Error consultando detalle pagos_factura: {e}")
        
        # Tabla cheques temporal
        cursor.execute("SHOW TABLES LIKE 'cheques'")
        if cursor.fetchone():
            try:
                cursor.execute("""
                    SELECT 
                        COALESCE(c.numero_cheque, 'N/A') as numero_cheque,
                        COALESCE(c.monto, 0) as monto,
                        COALESCE(p.nombre, 'Proveedor Desconocido') as proveedor,
                        'Pendiente' as estado,
                        'Tabla Temporal' as origen
                    FROM cheques c
                    LEFT JOIN proveedores p ON c.proveedor_id = p.id
                    WHERE DATE(c.fecha_cheque) = %s
                    ORDER BY c.numero_cheque
                """, (fecha_especifica,))
                
                cheques_temporal = cursor.fetchall()
                todos_cheques.extend(cheques_temporal)
                
            except Exception as e:
                logger.warning(f"Error consultando detalle tabla cheques: {e}")
        
        # Procesar resultados
        cheques_procesados = []
        total_monto = 0
        
        for cheque in todos_cheques:
            monto = safe_float(cheque["monto"])
            total_monto += monto
            
            cheques_procesados.append({
                "numero_cheque": cheque["numero_cheque"],
                "monto": monto,
                "proveedor": cheque["proveedor"],
                "estado": cheque["estado"],
                "origen": cheque["origen"]
            })
        
        return {
            "fecha": fecha_especifica,
            "total_cheques": len(cheques_procesados),
            "total_monto": round(total_monto, 2),
            "cheques": cheques_procesados
        }
        
    except Exception as e:
        logger.error(f"Error en /calendario-cheques/detalle: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener detalle de cheques: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.get("/resumen-financiero", response_class=JSONResponse)
def obtener_resumen_financiero():
    """Obtener resumen financiero con facturas y pagos"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        resumen = {}

        # Facturas por estado
        try:
            cursor.execute("""
                SELECT 
                    COALESCE(estado, 'Sin Estado') as estado,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(total), 0) as monto_total
                FROM facturas_compra
                GROUP BY estado
            """)
            resumen["facturas"] = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Error consultando facturas: {e}")
            resumen["facturas"] = []

        # Devoluciones
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_devoluciones,
                    COALESCE(SUM(monto_indemnizacion), 0) as monto_devoluciones
                FROM devoluciones
            """)
            devoluciones = cursor.fetchone()
            resumen["devoluciones"] = {
                "total": safe_int(devoluciones["total_devoluciones"] if devoluciones else 0),
                "monto": safe_float(devoluciones["monto_devoluciones"] if devoluciones else 0)
            }
        except Exception as e:
            logger.warning(f"Error consultando devoluciones: {e}")
            resumen["devoluciones"] = {"total": 0, "monto": 0}

        # Órdenes de producción
        try:
            cursor.execute("""
                SELECT 
                    COALESCE(tipo, 'Sin Tipo') as tipo,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(precio_reparacion), 0) as costo_total
                FROM produccion
                GROUP BY tipo
            """)
            resumen["produccion"] = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Error consultando producción: {e}")
            resumen["produccion"] = []

        return resumen

    except Exception as e:
        logger.error(f"Error en /resumen-financiero: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener resumen financiero: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.post("/comparar-ventas", response_class=JSONResponse)
def comparar_ventas(request: ComparacionRequest):
    """Comparar ventas entre dos períodos"""
    conn = None
    cursor = None
    
    try:
        conn = conectar_mysql()
        
        def calcular_ventas_periodo(desde, hasta):
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT 
                    COALESCE(SUM(v.precio), 0) as total_vendido,
                    COALESCE(SUM(v.unidades), 0) as total_unidades,
                    COALESCE(SUM(
                        v.precio - 
                        COALESCE(v.costo_despacho, 0) - 
                        (v.precio * 0.19) - 
                        (v.precio * COALESCE(c.porcentaje_comision, 0) / 100)
                    ), 0) as total_neto
                FROM ventas_retail v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                WHERE v.fecha_compra BETWEEN %s AND %s
            """
            cursor.execute(query, (desde, hasta))
            resultado = cursor.fetchone()
            
            return {
                "total": safe_float(resultado["total_vendido"]),
                "unidades": safe_int(resultado["total_unidades"]),
                "neto": safe_float(resultado["total_neto"])
            }

        periodo_a = calcular_ventas_periodo(request.periodo_a.desde, request.periodo_a.hasta)
        periodo_b = calcular_ventas_periodo(request.periodo_b.desde, request.periodo_b.hasta)

        return {
            "periodo_a": periodo_a,
            "periodo_b": periodo_b
        }

    except Exception as e:
        logger.error(f"Error en /comparar-ventas: {e}")
        raise HTTPException(status_code=500, detail=f"Error al comparar ventas: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()