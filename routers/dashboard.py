from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
from datetime import datetime, timedelta

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")

class Periodo(BaseModel):
    desde: str  # formato "YYYY-MM-DD"
    hasta: str

class ComparacionRequest(BaseModel):
    periodo_a: Periodo
    periodo_b: Periodo

def calcular_ventas(conn, desde, hasta):
    cursor = conn.cursor(dictionary=True)
    
    query = f"""
        SELECT 
            v.precio,
            v.costo_despacho,
            v.unidades,
            c.porcentaje_comision
        FROM ventas_retail v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.fecha_compra BETWEEN %s AND %s
    """
    cursor.execute(query, (desde, hasta))
    rows = cursor.fetchall()

    total_unidades = 0
    total_vendido = 0
    total_neto = 0

    for row in rows:
        unidades = row.get("unidades") or 0
        precio = row.get("precio") or 0
        despacho = row.get("costo_despacho") or 0
        comision = row.get("porcentaje_comision") or 0

        total_unidades += unidades
        total_vendido += precio

        # Calcular neto: descontar IVA, despacho, comisión
        iva = precio * 0.19
        comision_monto = precio * (comision / 100)
        neto = precio - despacho - iva - comision_monto

        total_neto += neto

    return {
        "unidades": total_unidades,
        "total": round(total_vendido, 2),
        "neto": round(total_neto, 2)
    }

@router.get("/", response_class=HTMLResponse)
def vista_dashboard(request: Request):
    """Vista principal del dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/totales", response_class=JSONResponse)
def obtener_totales_generales():
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                v.precio,
                v.costo_despacho,
                v.unidades,
                c.porcentaje_comision
            FROM ventas_retail v
            JOIN clientes c ON v.cliente_id = c.id
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        total_unidades = 0
        total_vendido = 0
        total_neto = 0

        for row in rows:
            unidades = row.get("unidades") or 0
            precio = float(row.get("precio") or 0)
            despacho = float(row.get("costo_despacho") or 0)
            comision = float(row.get("porcentaje_comision") or 0)

            iva = precio * 0.19
            comision_monto = precio * (comision / 100)
            neto = precio - despacho - iva - comision_monto

            total_unidades += unidades
            total_vendido += precio
            total_neto += neto

        return {
            "unidades": total_unidades,
            "total": round(total_vendido, 2),
            "neto": round(total_neto, 2)
        }

    except Exception as e:
        print("❌ ERROR EN /totales:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")

    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/kpis", response_class=JSONResponse)
def obtener_kpis(fecha_desde: str = "", fecha_hasta: str = ""):
    """Obtener KPIs principales del dashboard con filtros de fecha"""
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

        # Total de ventas con filtros
        query_totales = f"""
            SELECT 
                COUNT(*) as total_ordenes,
                SUM(v.precio) as total_ventas,
                SUM(v.unidades) as total_unidades,
                SUM(v.precio - v.costo_despacho - (v.precio * 0.19) - (v.precio * c.porcentaje_comision / 100)) as margen_neto
            FROM ventas_retail v
            JOIN clientes c ON v.cliente_id = c.id
            {where_clause}
        """
        cursor.execute(query_totales, params)
        totales = cursor.fetchone()

        # Facturas pendientes (sin filtro de fecha ya que es estado actual)
        cursor.execute("""
            SELECT COUNT(*) as facturas_pendientes
            FROM facturas_compra
            WHERE estado = 'pendiente'
        """)
        facturas_pendientes = cursor.fetchone()

        return {
            "total_ventas": round(totales["total_ventas"] or 0, 2),
            "total_unidades": totales["total_unidades"] or 0,
            "total_ordenes": totales["total_ordenes"] or 0,
            "margen_neto": round(totales["margen_neto"] or 0, 2),
            "facturas_pendientes": facturas_pendientes["facturas_pendientes"] or 0
        }

    except Exception as e:
        print("❌ ERROR EN /kpis:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/ventas-tendencia", response_class=JSONResponse)
def obtener_tendencia_ventas(dias: int = 7):
    """Obtener tendencia de ventas por día"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Calcular fecha de inicio
        fecha_fin = datetime.now()
        fecha_inicio = fecha_fin - timedelta(days=dias)

        query = """
            SELECT 
                DATE(v.fecha_compra) as fecha,
                SUM(v.precio) as total_dia,
                COUNT(*) as ordenes_dia
            FROM ventas_retail v
            WHERE v.fecha_compra >= %s AND v.fecha_compra <= %s
            GROUP BY DATE(v.fecha_compra)
            ORDER BY fecha
        """
        
        cursor.execute(query, (fecha_inicio.date(), fecha_fin.date()))
        resultados = cursor.fetchall()

        # Formatear datos para el gráfico
        fechas = []
        ventas = []
        ordenes = []

        for row in resultados:
            fechas.append(row["fecha"].strftime("%d/%m"))
            ventas.append(float(row["total_dia"] or 0))
            ordenes.append(row["ordenes_dia"] or 0)

        return {
            "fechas": fechas,
            "ventas": ventas,
            "ordenes": ordenes
        }

    except Exception as e:
        print("❌ ERROR EN /ventas-tendencia:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/top-clientes", response_class=JSONResponse)
def obtener_top_clientes(limite: int = 5, fecha_desde: str = "", fecha_hasta: str = ""):
    """Obtener top clientes por volumen de ventas"""
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
                c.nombre,
                SUM(v.precio) as total_ventas,
                COUNT(*) as total_ordenes
            FROM ventas_retail v
            JOIN clientes c ON v.cliente_id = c.id
            {where_clause}
            GROUP BY c.id, c.nombre
            ORDER BY total_ventas DESC
            LIMIT %s
        """
        
        print(f"📊 Query top clientes: {query}")
        print(f"📊 Parámetros: {params}")
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        print(f"📊 Clientes encontrados: {len(resultados)}")

        clientes = []
        for row in resultados:
            clientes.append({
                "nombre": row["nombre"],
                "total_ventas": round(float(row["total_ventas"] or 0), 2),
                "total_ordenes": row["total_ordenes"] or 0
            })

        return {"clientes": clientes}

    except Exception as e:
        print("❌ ERROR EN /top-clientes:", e)
        raise HTTPException(status_code=500, detail=f"Error interno en el cálculo: {str(e)}")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@router.get("/productos-mensuales", response_class=JSONResponse)
def obtener_productos_mensuales(fecha_desde: str = "", fecha_hasta: str = "", limite: int = 5):
    """Obtener productos más vendidos agrupados por mes"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Construir filtros de fecha
        filtros = ["v.producto IS NOT NULL", "v.producto != ''"]
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
                v.producto,
                SUM(v.unidades) as total_unidades,
                SUM(v.precio) as total_ventas,
                COUNT(*) as total_ordenes
            FROM ventas_retail v
            {where_clause}
            GROUP BY DATE_FORMAT(v.fecha_compra, '%Y-%m'), v.producto
            ORDER BY mes DESC, total_unidades DESC
        """
        
        print(f"📊 Query productos mensuales: {query}")
        print(f"📊 Parámetros: {params}")
        
        cursor.execute(query, params)
        resultados = cursor.fetchall()
        
        print(f"📊 Resultados encontrados: {len(resultados)}")

        # Organizar datos por mes
        datos_por_mes = {}
        for row in resultados:
            mes = row["mes"]
            if mes not in datos_por_mes:
                datos_por_mes[mes] = []
            
            if len(datos_por_mes[mes]) < limite:
                datos_por_mes[mes].append({
                    "producto": row["producto"],
                    "total_unidades": row["total_unidades"] or 0,
                    "total_ventas": round(float(row["total_ventas"] or 0), 2),
                    "total_ordenes": row["total_ordenes"] or 0
                })

        print(f"📊 Datos organizados por mes: {datos_por_mes}")
        return {"datos_por_mes": datos_por_mes}

    except Exception as e:
        print("❌ ERROR EN /productos-mensuales:", e)
        raise HTTPException(status_code=500, detail=f"Error interno en el cálculo: {str(e)}")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@router.get("/calendario-cheques", response_class=JSONResponse)
def obtener_calendario_cheques(año: int = None, mes: int = None):
    """Obtener calendario de cheques combinando pagos_factura y tabla cheques"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Si no se especifica año/mes, usar actual
        if not año or not mes:
            hoy = datetime.now()
            año = año or hoy.year
            mes = mes or hoy.month

        # Query combinada usando UNION para mezclar ambas tablas
        query = """
            -- Cheques del sistema actual (pagos_factura)
            SELECT 
                DATE(pf.fecha) as fecha_cheque,
                COUNT(*) as cantidad_cheques,
                SUM(pf.monto) as monto_total,
                'sistema' as origen
            FROM pagos_factura pf
            WHERE pf.tipo = 'cheque' 
            AND YEAR(pf.fecha) = %s 
            AND MONTH(pf.fecha) = %s
            GROUP BY DATE(pf.fecha)
            
            UNION ALL
            
            -- Cheques de la tabla temporal
            SELECT 
                DATE(c.fecha_cheque) as fecha_cheque,
                COUNT(*) as cantidad_cheques,
                SUM(c.monto) as monto_total,
                'temporal' as origen
            FROM cheques c
            WHERE YEAR(c.fecha_cheque) = %s 
            AND MONTH(c.fecha_cheque) = %s
            GROUP BY DATE(c.fecha_cheque)
        """
        
        cursor.execute(query, (año, mes, año, mes))
        resultados = cursor.fetchall()

        # Agrupar por fecha combinando ambos orígenes
        dias_con_cheques = {}
        
        for resultado in resultados:
            dia = resultado["fecha_cheque"].day
            
            if dia not in dias_con_cheques:
                dias_con_cheques[dia] = {
                    "cantidad": 0,
                    "monto": 0,
                    "detalles": {
                        "sistema": {"cantidad": 0, "monto": 0},
                        "temporal": {"cantidad": 0, "monto": 0}
                    }
                }
            
            # Sumar totales
            dias_con_cheques[dia]["cantidad"] += resultado["cantidad_cheques"]
            dias_con_cheques[dia]["monto"] += float(resultado["monto_total"] or 0)
            
            # Guardar detalles por origen
            origen = resultado["origen"]
            dias_con_cheques[dia]["detalles"][origen]["cantidad"] = resultado["cantidad_cheques"]
            dias_con_cheques[dia]["detalles"][origen]["monto"] = float(resultado["monto_total"] or 0)

        # Redondear montos
        for dia in dias_con_cheques:
            dias_con_cheques[dia]["monto"] = round(dias_con_cheques[dia]["monto"], 2)

        return {
            "año": año,
            "mes": mes,
            "dias_con_cheques": dias_con_cheques
        }

    except Exception as e:
        print("❌ ERROR EN /calendario-cheques:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@router.get("/calendario-cheques/detalle", response_class=JSONResponse)
def obtener_detalle_dia_cheques(año: int, mes: int, dia: int):
    """Obtener detalle de cheques para un día específico"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)
        
        fecha_especifica = f"{año}-{mes:02d}-{dia:02d}"
        
        # Cheques del sistema actual
        cursor.execute("""
            SELECT 
                pf.numero as numero_cheque,
                pf.monto,
                p.nombre as proveedor,
                pf.estado,
                'Sistema Actual' as origen
            FROM pagos_factura pf
            JOIN facturas_compra f ON f.id = pf.factura_id
            JOIN proveedores p ON f.proveedor_id = p.id
            WHERE pf.tipo = 'cheque' 
            AND DATE(pf.fecha) = %s
            ORDER BY pf.numero
        """, (fecha_especifica,))
        
        cheques_sistema = cursor.fetchall()
        
        # Cheques de tabla temporal
        cursor.execute("""
            SELECT 
                c.numero_cheque,
                c.monto,
                p.nombre as proveedor,
                'Pendiente' as estado,
                'Tabla Temporal' as origen
            FROM cheques c
            JOIN proveedores p ON c.proveedor_id = p.id
            WHERE DATE(c.fecha_cheque) = %s
            ORDER BY c.numero_cheque
        """, (fecha_especifica,))
        
        cheques_temporal = cursor.fetchall()
        
        # Combinar ambos resultados
        todos_cheques = cheques_sistema + cheques_temporal
        
        return {
            "fecha": fecha_especifica,
            "total_cheques": len(todos_cheques),
            "total_monto": sum(float(c["monto"]) for c in todos_cheques),
            "cheques": todos_cheques,
            "resumen": {
                "sistema": len(cheques_sistema),
                "temporal": len(cheques_temporal)
            }
        }
        
    except Exception as e:
        print("❌ ERROR EN /calendario-cheques/detalle:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

@router.get("/resumen-financiero", response_class=JSONResponse)
def obtener_resumen_financiero():
    """Obtener resumen financiero con facturas y pagos"""
    try:
        conn = conectar_mysql()
        cursor = conn.cursor(dictionary=True)

        # Facturas por estado
        cursor.execute("""
            SELECT 
                estado,
                COUNT(*) as cantidad,
                SUM(total) as monto_total
            FROM facturas_compra
            GROUP BY estado
        """)
        facturas = cursor.fetchall()

        # Devoluciones
        cursor.execute("""
            SELECT 
                COUNT(*) as total_devoluciones,
                SUM(monto_indemnizacion) as monto_devoluciones
            FROM devoluciones
        """)
        devoluciones = cursor.fetchone()

        # Órdenes de producción
        cursor.execute("""
            SELECT 
                tipo,
                COUNT(*) as cantidad,
                SUM(precio_reparacion) as costo_total
            FROM produccion
            GROUP BY tipo
        """)
        produccion = cursor.fetchall()

        return {
            "facturas": facturas,
            "devoluciones": {
                "total": devoluciones["total_devoluciones"] or 0,
                "monto": round(float(devoluciones["monto_devoluciones"] or 0), 2)
            },
            "produccion": produccion
        }

    except Exception as e:
        print("❌ ERROR EN /resumen-financiero:", e)
        raise HTTPException(status_code=500, detail="Error interno en el cálculo.")
    finally:
        if 'conn' in locals():
            conn.close()

@router.post("/comparar-ventas", response_class=JSONResponse)
def comparar_ventas(request: ComparacionRequest):
    conn = conectar_mysql()

    try:
        periodo_a = calcular_ventas(conn, request.periodo_a.desde, request.periodo_a.hasta)
        periodo_b = calcular_ventas(conn, request.periodo_b.desde, request.periodo_b.hasta)

        return {
            "periodo_a": periodo_a,
            "periodo_b": periodo_b
        }

    except Exception as e:
        print("❌ ERROR en /dashboard/comparar-ventas:", e)
        raise HTTPException(status_code=500, detail="Error interno en el servidor.")
    finally:
        conn.close()