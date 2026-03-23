from fastapi import APIRouter, HTTPException
from db import conectar_mysql
from schemas.venta_schema import VentaCreate, VentaOut
from pydantic import BaseModel
from typing import List
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import io
import pandas as pd
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
from collections import defaultdict
from schemas.venta_schema import VentaManualRequest, VentaManualResponse
from fastapi import Response, HTTPException
import csv


router = APIRouter(prefix="/ventas", tags=["Ventas"])

@router.get("/", response_model=list[VentaOut])
def obtener_ventas():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True, buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        cursor.execute("""
            SELECT 
                vr.id,
                vr.numero_orden,
                c.nombre AS cliente,
                vr.producto,
                vr.fecha_entrega,
                vr.estado,
                vr.sku
            FROM ventas_retail vr
            JOIN clientes c ON vr.cliente_id = c.id
            ORDER BY vr.fecha_entrega DESC
        """)
        resultados = cursor.fetchall()

        # Validar fechas nulas
        for r in resultados:
            fecha = r["fecha_entrega"]
            r["fecha_entrega"] = fecha.strftime("%Y-%m-%d") if fecha else ""

        return resultados
    
    except Exception as e:
        print(f"Error en obtener_ventas: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


@router.post("/", response_model=VentaOut)
def crear_venta(venta: VentaCreate):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True, buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        # Log de datos recibidos para debugging
        print(f"📥 Datos de venta recibidos: {venta.dict()}")
        
        # Validaciones básicas
        if not venta.cliente_final or not venta.cliente_final.strip():
            raise HTTPException(status_code=400, detail="cliente_final es obligatorio")
        
        if not venta.producto or not venta.producto.strip():
            raise HTTPException(status_code=400, detail="producto es obligatorio")
        
        if venta.precio is None or venta.precio < 0:
            raise HTTPException(status_code=400, detail="precio debe ser mayor o igual a 0")
        
        # Definir columnas exactamente como están en la base de datos
        columnas = [
            "cliente_id", "numero_orden", "cliente_final", "rut_documento", "email",
            "telefono", "fecha_entrega", "fecha_cliente", "producto", "precio",
            "precio_cliente", "costo_despacho", "comuna", "direccion", "region",
            "sku", "estado", "documento", "razon_social", "rut", "giro",
            "direccion_factura", "courier", "unidades", "users_id", "fecha_compra"
        ]
        
        # Obtener valores, usando valores por defecto para campos opcionales
        valores = [
            venta.cliente_id or 1,
            venta.numero_orden or f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            venta.cliente_final.strip(),
            venta.rut_documento or "",
            venta.email or "",
            venta.telefono or "",
            venta.fecha_entrega or datetime.now().date(),
            venta.fecha_cliente or datetime.now().date(),
            venta.producto.strip(),
            venta.precio or 0,
            venta.precio_cliente or venta.precio or 0,
            venta.costo_despacho or 0,
            venta.comuna or "",
            venta.direccion or "",
            venta.region or "",
            venta.sku or "",
            venta.estado or "nueva",
            venta.documento or "boleta",
            venta.razon_social or venta.cliente_final or "",
            venta.rut or venta.rut_documento or "",
            venta.giro or "Particular",
            venta.direccion_factura or venta.direccion or "",
            venta.courier or "Retiro en tienda",
            venta.unidades or 1,
            venta.users_id or 1,
            venta.fecha_compra or datetime.now().date()
        ]

        placeholders = ", ".join(["%s"] * len(columnas))
        columnas_str = ", ".join(columnas)

        query = f"""
            INSERT INTO ventas_retail ({columnas_str})
            VALUES ({placeholders})
        """
        
        print(f"🔄 Ejecutando query: {query}")
        print(f"📊 Valores: {valores}")
        
        cursor.execute(query, valores)
        conn.commit()
        
        venta_id = cursor.lastrowid
        print(f"✅ Venta creada con ID: {venta_id}")
        
        # Retornar la venta creada
        venta_dict = venta.dict()
        venta_dict["id"] = venta_id
        venta_dict["fecha_entrega"] = str(valores[columnas.index("fecha_entrega")])
        venta_dict["fecha_compra"] = str(valores[columnas.index("fecha_compra")])

        return venta_dict
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error en crear_venta: {e}")
        
        # Proporcionar más detalles del error
        if "Duplicate entry" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe una venta con ese número de orden")
        elif "cannot be null" in str(e):
            raise HTTPException(status_code=400, detail=f"Campo obligatorio faltante: {str(e)}")
        elif "Data too long" in str(e):
            raise HTTPException(status_code=400, detail=f"Datos demasiado largos: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"Error al crear venta: {str(e)}")
    finally:
        cursor.close()
        conn.close()


class EstadoUpdate(BaseModel):
    ids: List[int]
    estado: str

@router.put("/cambiar-estado")
def cambiar_estado_ventas(data: EstadoUpdate):
    conn = conectar_mysql()
    cursor = conn.cursor(buffered=True)  # ✅ AGREGADO BUFFERED=TRUE

    try:
        formato = ", ".join(["%s"] * len(data.ids))
        query = f"UPDATE ventas_retail SET estado = %s WHERE id IN ({formato})"
        cursor.execute(query, (data.estado, *data.ids))
        conn.commit()
        return {"mensaje": f"{cursor.rowcount} ventas actualizadas a '{data.estado}'."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()


class EliminarVentas(BaseModel):
    ids: List[int]

@router.post("/eliminar-varias")
def eliminar_varias_ventas(data: EliminarVentas):
    conn = conectar_mysql()
    cursor = conn.cursor(buffered=True)  # ✅ AGREGADO BUFFERED=TRUE
    
    try:
        placeholders = ", ".join(["%s"] * len(data.ids))
        query = f"DELETE FROM ventas_retail WHERE id IN ({placeholders})"
        cursor.execute(query, data.ids)
        conn.commit()
        return {"mensaje": f"{cursor.rowcount} ventas eliminadas correctamente."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

templates = Jinja2Templates(directory="templates")

@router.get("/vista", response_class=HTMLResponse)
def vista_ventas(
    request: Request,
    cliente: str = "",
    orden: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = "",
    ordenarPor: str = "fecha_entrega",
    direccion: str = "desc"
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    filtros = []
    params = []

    if cliente:
        filtros.append("c.nombre LIKE %s")
        params.append(f"%{cliente}%")
    if orden:
        filtros.append("vr.numero_orden LIKE %s")
        params.append(f"%{orden}%")
    if desde:
        filtros.append("vr.fecha_entrega >= %s")
        params.append(desde)
    if hasta:
        filtros.append("vr.fecha_entrega <= %s")
        params.append(hasta)
    if estado:
        filtros.append("vr.estado = %s")
        params.append(estado)

    where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

    # Validar campos para evitar SQL injection
    columnas_validas = ["numero_orden", "cliente", "producto", "fecha_entrega", "estado"]
    direcciones_validas = ["asc", "desc"]

    if ordenarPor not in columnas_validas:
        ordenarPor = "fecha_entrega"
    if direccion not in direcciones_validas:
        direccion = "desc"

    # Traducir nombre de columna
    orden_columna = "c.nombre" if ordenarPor == "cliente" else f"vr.{ordenarPor}"

    cursor.execute(f"""
        SELECT 
            vr.id,
            vr.numero_orden,
            c.nombre AS cliente,
            vr.producto,
            vr.fecha_entrega,
            vr.estado,
            vr.sku
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        ORDER BY {orden_columna} {direccion}
        LIMIT 500
    """, params)

    ventas = cursor.fetchall()
    for v in ventas:
        fecha = v["fecha_entrega"]
        v["fecha_entrega"] = fecha.strftime("%d-%m-%Y") if fecha else ""

    conn.close()

    hx_request = request.headers.get("HX-Request")
    
    contexto = {
        "request": request,
        "ventas": ventas,
        "ordenar_por": ordenarPor,
        "direccion": direccion
    }

    if hx_request:
        return templates.TemplateResponse("partials/tabla_ventas.html", contexto)
    else:
        return templates.TemplateResponse("ventas.html", contexto)

@router.get("/tabla", response_class=HTMLResponse)
def tabla_ventas(request: Request,
                 cliente: str = "",
                 orden: str = "",
                 desde: str = "",
                 hasta: str = "",
                 estado: str = ""):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    filtros = []
    params = []

    if cliente:
        filtros.append("c.nombre LIKE %s")
        params.append(f"%{cliente}%")
    if orden:
        filtros.append("vr.numero_orden LIKE %s")
        params.append(f"%{orden}%")
    if desde:
        filtros.append("vr.fecha_entrega >= %s")
        params.append(desde)
    if hasta:
        filtros.append("vr.fecha_entrega <= %s")
        params.append(hasta)
    if estado:
        filtros.append("vr.estado = %s")
        params.append(estado)

    where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

    cursor.execute(f"""
        SELECT 
            vr.id,
            vr.numero_orden,
            c.nombre AS cliente,
            vr.producto,
            vr.fecha_entrega,
            vr.estado,
            vr.sku
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        ORDER BY vr.fecha_entrega DESC
        LIMIT 500
    """, params)

    ventas = cursor.fetchall()
    for v in ventas:
        fecha = v["fecha_entrega"]
        v["fecha_entrega"] = fecha.strftime("%d-%m-%Y") if fecha else ""

    conn.close()
    return templates.TemplateResponse("partials/tabla_ventas.html", {
        "request": request,
        "ventas": ventas
    })

@router.get("/maestra", response_class=HTMLResponse)
async def vista_maestra(request: Request):
    """Vista principal de la maestra de ventas"""
    return templates.TemplateResponse("ventas/maestra.html", {"request": request})

@router.get("/maestra/datos", response_class=HTMLResponse)
async def datos_maestra(
    request: Request,
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""  # Filtrar por estado desde ventas_retail
):
    """Obtener datos de la maestra con filtros"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Si no hay fechas, usar últimos 7 días
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        # Construir filtros
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        
        # FILTRO POR ESTADO desde ventas_retail
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        # Consulta principal
        query = f"""
        SELECT 
            c.nombre as cliente,
            vr.producto,
            vr.estado as estado_producto,
            DATE(vr.fecha_entrega) as fecha,
            COUNT(*) as cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        # Procesar datos
        tabla_datos = procesar_datos_maestra(datos, estado_producto)
        
        return templates.TemplateResponse("partials/tabla_maestra.html", {
            "request": request,
            "tabla_datos": tabla_datos,
            "filtro_estado": estado_producto
        })
        
    except Exception as e:
        return f"<div class='p-4 text-red-600'>Error: {str(e)}</div>"
    finally:
        cursor.close()
        conn.close()

def procesar_datos_maestra(datos, estado_filtro=None):
    """Procesa los datos para crear la estructura de tabla dinámica"""
    
    # Organizar datos
    tabla = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    fechas = set()
    productos_estados = {}  # Para trackear el estado de cada producto
    
    for row in datos:
        cliente = row['cliente']
        producto = row['producto']
        fecha = row['fecha'].strftime('%d-%m-%Y')
        cantidad = row['cantidad']
        estado_producto = row.get('estado_producto', '')
        
        fechas.add(fecha)
        tabla[cliente][producto][fecha] += cantidad
        productos_estados[producto] = estado_producto
    
    # Ordenar fechas
    fechas_ordenadas = sorted(list(fechas), key=lambda x: datetime.strptime(x, '%d-%m-%Y'))
    
    # Calcular totales
    tabla_con_totales = {}
    totales_por_fecha = {fecha: 0 for fecha in fechas_ordenadas}
    gran_total = 0
    
    for cliente, productos in tabla.items():
        tabla_con_totales[cliente] = {
            'productos': {},
            'totales_por_fecha': {fecha: 0 for fecha in fechas_ordenadas},
            'total_cliente': 0
        }
        
        for producto, fechas_dict in productos.items():
            # Calcular total por producto
            total_producto = sum(fechas_dict.values())
            estado_producto = productos_estados.get(producto, '')
            
            tabla_con_totales[cliente]['productos'][producto] = {
                'fechas': dict(fechas_dict),
                'total': total_producto,
                'estado': estado_producto,
                'es_nuevo': estado_producto.lower() == 'nueva'  # Flag para productos nuevos
            }
            
            # Acumular totales por fecha para este cliente
            for fecha, cantidad in fechas_dict.items():
                tabla_con_totales[cliente]['totales_por_fecha'][fecha] += cantidad
                totales_por_fecha[fecha] += cantidad
                gran_total += cantidad
            
            tabla_con_totales[cliente]['total_cliente'] += total_producto
    
    return {
        'clientes': tabla_con_totales,
        'fechas': fechas_ordenadas,
        'totales_por_fecha': totales_por_fecha,
        'gran_total': gran_total,
        'estado_filtro': estado_filtro,
        'solo_productos_nuevos': estado_filtro == 'nueva'
    }

@router.get("/maestra/exportar/excel")
async def exportar_excel_maestra(
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""
):
    """Exportar a Excel con filtro de estado desde ventas_retail"""
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Aplicar misma lógica de filtros que en datos_maestra
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        query = f"""
        SELECT 
            c.nombre as Cliente,
            vr.producto as Producto,
            vr.estado as 'Estado Producto',
            DATE(vr.fecha_entrega) as Fecha,
            COUNT(*) as Cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, Fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")
        
        # Crear DataFrame
        df = pd.DataFrame(datos)
        
        # Formatear la fecha
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%d/%m/%Y')
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja principal
            df.to_excel(writer, sheet_name='Maestra Ventas', index=False)
            
            # Agregar hoja de resumen si es filtro de productos nuevos
            if estado_producto == 'nueva':
                resumen_df = df.groupby(['Cliente', 'Producto']).agg({
                    'Cantidad': 'sum'
                }).reset_index()
                resumen_df.to_excel(writer, sheet_name='Resumen Productos Nuevos', index=False)
                
                # Hoja de estadísticas por cliente
                stats_cliente = df.groupby('Cliente').agg({
                    'Cantidad': 'sum',
                    'Producto': 'nunique'
                }).reset_index()
                stats_cliente.columns = ['Cliente', 'Total Ventas', 'Productos Diferentes']
                stats_cliente.to_excel(writer, sheet_name='Stats por Cliente', index=False)
        
        output.seek(0)
        
        # Nombre del archivo con indicador de filtro
        nombre_archivo = f"maestra_ventas"
        if estado_producto == 'nueva':
            nombre_archivo += "_productos_nuevos"
        nombre_archivo += f"_{fecha_desde}_{fecha_hasta}.xlsx"
        
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar Excel: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/maestra/exportar/pdf") 
async def exportar_pdf_maestra(
    fecha_desde: str = "",
    fecha_hasta: str = "",
    cliente: str = "",
    producto: str = "",
    estado_producto: str = ""
):
    """Exportar a PDF con filtro de estado desde ventas_retail"""
    
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Aplicar misma lógica de filtros
        if not fecha_desde or not fecha_hasta:
            hoy = datetime.now()
            hace_7_dias = hoy - timedelta(days=7)
            fecha_desde = fecha_desde or hace_7_dias.strftime('%Y-%m-%d')
            fecha_hasta = fecha_hasta or hoy.strftime('%Y-%m-%d')
        
        filtros = ["vr.fecha_entrega >= %s", "vr.fecha_entrega <= %s"]
        params = [fecha_desde, fecha_hasta]
        
        if cliente:
            filtros.append("c.id = %s")
            params.append(cliente)
        if producto:
            filtros.append("vr.producto LIKE %s")
            params.append(f"%{producto}%")
        if estado_producto:
            filtros.append("vr.estado = %s")
            params.append(estado_producto)
            
        where_clause = "WHERE " + " AND ".join(filtros)
        
        query = f"""
        SELECT 
            c.nombre as cliente,
            vr.producto,
            vr.estado as estado_producto,
            DATE(vr.fecha_entrega) as fecha,
            COUNT(*) as cantidad
        FROM ventas_retail vr
        JOIN clientes c ON vr.cliente_id = c.id
        {where_clause}
        GROUP BY c.nombre, vr.producto, vr.estado, DATE(vr.fecha_entrega)
        ORDER BY c.nombre, vr.producto, fecha
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")
        
        # Crear HTML para el PDF
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Maestra de Ventas - Productos Nuevos</title>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 20px; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                .header h1 {{ margin: 0; color: #333; }}
                .header h2 {{ margin: 5px 0; color: #059669; }}
                .filters {{ margin-bottom: 15px; background: #f5f5f5; padding: 10px; border-radius: 5px; }}
                .stats {{ margin-bottom: 15px; background: #e3f2fd; padding: 10px; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .nuevo {{ background-color: #e8f5e8; }}
                .total-row {{ background-color: #f0f0f0; font-weight: bold; }}
                .footer {{ margin-top: 20px; text-align: center; font-size: 10px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>MAESTRA DE VENTAS POR CLIENTE</h1>
                {'<h2>★ SOLO PRODUCTOS NUEVOS ★</h2>' if estado_producto == 'nueva' else '<h2>Todos los Estados</h2>'}
            </div>
            
            <div class="filters">
                <strong>📊 Filtros aplicados:</strong><br>
                📅 <strong>Período:</strong> {fecha_desde} al {fecha_hasta}<br>
                👤 <strong>Cliente:</strong> {cliente or 'Todos'}<br>
                📦 <strong>Producto:</strong> {producto or 'Todos'}<br>
                ⭐ <strong>Estado:</strong> {estado_producto.title() if estado_producto else 'Todos los estados'}
            </div>
            
            <div class="stats">
                <strong>📈 Resumen:</strong>
                Total de registros: {len(datos)} | 
                Clientes únicos: {len(set(row['cliente'] for row in datos))} | 
                Productos únicos: {len(set(row['producto'] for row in datos))} |
                Total ventas: {sum(row['cantidad'] for row in datos)}
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Cliente</th>
                        <th>Producto</th>
                        <th>Estado</th>
                        <th>Fecha</th>
                        <th>Cantidad</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for row in datos:
            clase_fila = 'nuevo' if row['estado_producto'] == 'nueva' else ''
            icono_estado = '⭐' if row['estado_producto'] == 'nueva' else '📦'
            
            html_content += f"""
                    <tr class="{clase_fila}">
                        <td>{row['cliente']}</td>
                        <td>{icono_estado} {row['producto']}</td>
                        <td>{row['estado_producto'].title()}</td>
                        <td>{row['fecha'].strftime('%d/%m/%Y')}</td>
                        <td>{row['cantidad']}</td>
                    </tr>
            """
        
        html_content += f"""
                </tbody>
            </table>
            
            <div class="footer">
                <p>🏢 Sistema de Gestión de Ventas - JerkHome | 
                📅 Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} | 
                🔍 Filtro aplicado: {estado_producto.title() if estado_producto else 'Sin filtro de estado'}</p>
            </div>
        </body>
        </html>
        """
        
        # Retornar HTML como respuesta
        nombre_archivo = f"maestra_ventas"
        if estado_producto == 'nueva':
            nombre_archivo += "_productos_nuevos"
        nombre_archivo += f"_{fecha_desde}_{fecha_hasta}.html"
        
        return StreamingResponse(
            io.StringIO(html_content),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar PDF: {str(e)}")
    finally:
        cursor.close()
        conn.close()


@router.get("/productos/estados")
async def obtener_estados_productos():
    """Endpoint para obtener todos los estados de productos disponibles"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = "SELECT DISTINCT estado FROM ventas_retail WHERE estado IS NOT NULL ORDER BY estado"
        cursor.execute(query)
        estados = cursor.fetchall()
        
        return [{"value": row["estado"], "label": row["estado"].title()} for row in estados]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estados: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/cargar/falabella", response_class=HTMLResponse)
async def cargar_ventas_falabella(request: Request):
    return templates.TemplateResponse("ventas/cargar/falabella.html", {"request": request})

@router.get("/cargar/cencosud", response_class=HTMLResponse)
async def cargar_ventas_cencosud(request: Request):
    return templates.TemplateResponse("ventas/cargar/cencosud.html", {"request": request})

@router.get("/cargar/walmart", response_class=HTMLResponse)
async def cargar_ventas_walmart(request: Request):
    return templates.TemplateResponse("ventas/cargar/walmart.html", {"request": request})

@router.get("/cargar/ripley", response_class=HTMLResponse)
async def cargar_ventas_ripley(request: Request):
    return templates.TemplateResponse("ventas/cargar/ripley.html", {"request": request})

@router.get("/cargar/hites", response_class=HTMLResponse)
async def cargar_ventas_hites(request: Request):
    return templates.TemplateResponse("ventas/cargar/hites.html", {"request": request})

@router.get("/cargar/manual", response_class=HTMLResponse)
async def cargar_ventas_manual(request: Request):
    return templates.TemplateResponse("ventas/cargar/manual.html", {"request": request})

@router.get("/descargar/excel")
async def descargar_excel_ventas(
    cliente: str = "",
    orden: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = ""
):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        filtros, params = [], []
        if cliente:
            filtros.append("c.nombre LIKE %s"); params.append(f"%{cliente}%")
        if orden:
            filtros.append("vr.numero_orden LIKE %s"); params.append(f"%{orden}%")
        if desde:
            filtros.append("vr.fecha_entrega >= %s"); params.append(desde)
        if hasta:
            filtros.append("vr.fecha_entrega <= %s"); params.append(hasta)
        if estado:
            filtros.append("vr.estado = %s"); params.append(estado)

        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""

        # ✅ Agregamos SKU
        query = f"""
            SELECT 
                c.nombre          AS cliente_nombre,
                vr.numero_orden   AS numero_orden,
                vr.fecha_compra   AS fecha_compra,
                vr.fecha_entrega  AS fecha_envio,
                vr.sku            AS sku,
                vr.producto       AS producto,
                vr.precio_cliente AS precio_cliente
            FROM ventas_retail vr
            JOIN clientes c ON vr.cliente_id = c.id
            {where_clause}
            ORDER BY vr.fecha_compra DESC, c.nombre, vr.numero_orden
        """
        cursor.execute(query, params)
        datos = cursor.fetchall()

        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")

        import pandas as pd, io

        df = pd.DataFrame(datos)

        # ✅ Nuevas columnas “bonitas”
        df.columns = ['Cliente', 'Orden de Compra', 'Fecha Compra', 'Fecha Envío', 'SKU', 'Producto', 'Precio Cliente']

        # Tipos correctos
        df['Fecha Compra'] = pd.to_datetime(df['Fecha Compra'], errors='coerce')
        df['Fecha Envío']  = pd.to_datetime(df['Fecha Envío'], errors='coerce')
        df['Precio Cliente'] = pd.to_numeric(df['Precio Cliente'], errors='coerce').fillna(0)
        df['SKU'] = df['SKU'].fillna("").astype(str)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Ventas', index=False)
            ws = writer.sheets['Ventas']

            # Map cabeceras -> índice
            cols = {cell.value: idx + 1 for idx, cell in enumerate(ws[1])}

            # Formato fechas
            for col_name in ['Fecha Compra', 'Fecha Envío']:
                for col in ws.iter_cols(
                    min_col=cols[col_name], max_col=cols[col_name],
                    min_row=2, max_row=ws.max_row
                ):
                    for c in col:
                        c.number_format = 'DD/MM/YYYY'

            # Formato moneda (miles)
            for col in ws.iter_cols(
                min_col=cols['Precio Cliente'], max_col=cols['Precio Cliente'],
                min_row=2, max_row=ws.max_row
            ):
                for c in col:
                    c.number_format = '#,##0'

            # Auto ancho
            for column_cells in ws.columns:
                max_len = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells)
                ws.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 60)

            # Resumen por Cliente
            resumen_cliente = (
                df.groupby('Cliente', as_index=False)
                  .agg(**{
                      'Total Productos': ('Producto', 'count'),
                      'Total Ventas':    ('Precio Cliente', 'sum')
                  })
            )
            resumen_cliente.to_excel(writer, sheet_name='Resumen por Cliente', index=False)

            # ✅ Resumen por OC (ahora incluye SKU para que no se mezcle todo)
            resumen_oc = (
                df.groupby(['Cliente', 'Orden de Compra', 'SKU', 'Producto'], as_index=False)
                  .agg(**{
                      'Items': ('Producto', 'count'),
                      'Total OC': ('Precio Cliente', 'sum')
                  })
                  .sort_values(['Cliente', 'Orden de Compra'])
            )
            resumen_oc.to_excel(writer, sheet_name='Resumen por OC', index=False)

        output.seek(0)
        nombre_archivo = f"ventas_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar Excel: {str(e)}")
    finally:
        cursor.close()
        conn.close()


# Agregar estos endpoints al final de ventas.py

@router.get("/clientes-retail")
async def obtener_clientes_retail():
    """Obtener lista de clientes retail para dropdown Nubox"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener clientes que tienen ventas en ventas_retail
        query = """
        SELECT DISTINCT c.id, c.nombre 
        FROM clientes c
        INNER JOIN ventas_retail vr ON c.id = vr.cliente_id
        WHERE c.id IS NOT NULL
        ORDER BY c.nombre
        """
        
        cursor.execute(query)
        clientes = cursor.fetchall()
        
        return clientes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener clientes retail: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/descargar/nubox/{cliente_id}")
async def descargar_nubox_cliente(
    cliente_id: int,
    cliente: str = "",
    orden: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = ""
):
    """Descargar CSV formato Nubox para cliente específico"""
    
    conn = conectar_mysql()
    # Usamos buffered=True para asegurar que la lectura de datos sea completa
    cursor = conn.cursor(dictionary=True, buffered=True) 
    
    try:
        # 1. Construir filtros (Excluimos canceladas por defecto para Nubox)
        filtros = ["vr.cliente_id = %s", "vr.estado != 'cancelada'"]
        params = [cliente_id]

        if cliente:
            filtros.append("c.nombre LIKE %s")
            params.append(f"%{cliente}%")
        if orden:
            filtros.append("vr.numero_orden LIKE %s")
            params.append(f"%{orden}%")
        if desde:
            filtros.append("vr.fecha_compra >= %s")
            params.append(desde)
        if hasta:
            filtros.append("vr.fecha_compra <= %s")
            params.append(hasta)
        if estado:
            filtros.append("vr.estado = %s")
            params.append(estado)

        where_clause = "WHERE " + " AND ".join(filtros)

        # 2. Query principal
        query = f"""
            SELECT 
                vr.documento,
                vr.numero_orden,
                vr.fecha_entrega,
                vr.rut_documento,
                vr.rut,
                vr.cliente_final,
                vr.razon_social,
                vr.giro,
                vr.comuna,
                vr.direccion,
                vr.producto,
                vr.unidades,
                vr.precio_cliente,
                vr.costo_despacho,
                vr.email,
                c.nombre as cliente_nombre
            FROM ventas_retail vr
            JOIN clientes c ON vr.cliente_id = c.id
            {where_clause}
            ORDER BY vr.numero_orden, vr.producto
        """
        
        cursor.execute(query, params)
        datos = cursor.fetchall()
        
        if not datos:
            raise HTTPException(status_code=404, detail="No se encontraron datos para exportar")
        
        # 3. Procesar datos para Nubox (Llama a tu función procesar_datos_nubox)
        datos_nubox = procesar_datos_nubox(datos)
        
        # 4. Crear CSV en memoria (StringIO)
        output = io.StringIO()
        
        headers = [
            "TIPO", "FOLIO", "SECUENCIA", "FECHA", "RUT", "RAZONSOCIAL", 
            "GIRO", "COMUNA", "DIRECCION", "AFECTO", "PRODUCTO", 
            "DESCRIPCION", "CANTIDAD", "PRECIO", "PORCENTDSCTO", 
            "EMAIL", "TIPOSERVICIO", "PERIODODESDE", "PERIODOHASTA", 
            "FECHAVENCIMIENTO"
        ]
        
        # Nubox requiere punto y coma (;) y saltos de línea estándar
        writer = csv.writer(output, delimiter=';', lineterminator='\n')
        writer.writerow(headers)
        
        for row in datos_nubox:
            writer.writerow(row)
        
        # 5. Generar nombre de archivo SEGURO (Aquí estaba tu error de NoneType)
        # Usamos .get() y un fallback 'cliente' para evitar el error si el nombre es NULL
        nombre_raw = datos[0].get('cliente_nombre') or "cliente"
        cliente_nombre_limpio = str(nombre_raw).lower().replace(' ', '_')
        
        fecha_actual = datetime.now().strftime('%Y%m%d')
        nombre_archivo = f"nubox_{cliente_nombre_limpio}_{fecha_actual}.csv"
        
        # 6. Obtener el valor final y cerrar el buffer
        contenido_csv = output.getvalue()
        output.close()
        
        # 7. Retornar Response directo (Mucho más estable que StreamingResponse)
        return Response(
            content=contenido_csv,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={nombre_archivo}",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
        
    except Exception as e:
        print(f"❌ Error crítico en descargar_nubox: {str(e)}")
        # Enviamos el error detallado para saber si falla en otra parte
        raise HTTPException(status_code=500, detail=f"Error al generar archivo Nubox: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def limpiar_caracteres_especiales(texto):
    """Limpia caracteres especiales para compatibilidad con Nubox"""
    if not texto:
        return ""
    
    # Convertir a string si no lo es
    texto = str(texto)
    
    # Usar unidecode para convertir caracteres especiales
    import unicodedata
    
    # Normalizar caracteres Unicode
    texto = unicodedata.normalize('NFD', texto)
    
    # Quitar acentos y caracteres especiales
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    
    # Reemplazos específicos adicionales
    reemplazos = {
        'ñ': 'n', 'Ñ': 'N',
        'ç': 'c', 'Ç': 'C',
        '°': '', '§': '', '¨': '', '´': '', '`': '',
        '"': '', '"': '', ''': '', ''': '', 
        '–': '-', '—': '-', '…': '...',
        '€': 'EUR', '£': 'GBP', '¥': 'YEN'
    }
    
    # Aplicar reemplazos
    for original, reemplazo in reemplazos.items():
        texto = texto.replace(original, reemplazo)
    
    # Limpiar caracteres no ASCII restantes
    texto = ''.join(char if ord(char) < 128 else '' for char in texto)
    
    # Limpiar espacios extra
    texto = ' '.join(texto.split())
    
    return texto.strip()

def formatear_rut(rut):
    """Formatea RUT chileno con guión antes del dígito verificador"""
    if not rut:
        return ""
    
    # Limpiar RUT (quitar puntos, guiones, espacios)
    rut_limpio = ''.join(filter(str.isalnum, str(rut).upper()))
    
    if len(rut_limpio) < 2:
        return rut_limpio
    
    # Separar número y dígito verificador
    numero = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    # Retornar con formato: 12345678-9
    return f"{numero}-{dv}"

def procesar_datos_nubox(datos):
    """Procesa los datos según la lógica especificada para Nubox con protección anti-errores"""
    
    resultado = []
    folios_por_orden = {}
    folio_counter = 1
    
    from collections import defaultdict
    ordenes = defaultdict(list)
    
    # Agrupar datos por numero_orden
    for row in datos:
        num_orden = row.get('numero_orden') or "SIN_ORDEN"
        ordenes[num_orden].append(row)
    
    # Procesar cada orden
    for numero_orden, items in ordenes.items():
        if numero_orden not in folios_por_orden:
            folios_por_orden[numero_orden] = folio_counter
            folio_counter += 1
        
        folio_orden = folios_por_orden[numero_orden]
        secuencia_actual = defaultdict(int)
        
        for row in items:
            producto = row.get('producto') or "Producto"
            
            doc_raw = row.get('documento')
            documento = str(doc_raw).lower() if doc_raw else "boleta"
            
            secuencia_actual[producto] += 1
            secuencia = secuencia_actual[producto]
            
            tipo = "39" if documento == "boleta" else "33"
            
            if documento == "boleta":
                rut = formatear_rut(row.get('rut_documento'))
                razon_social = limpiar_caracteres_especiales(row.get('cliente_final') or "")
                giro = "Particular"
            else:
                rut = formatear_rut(row.get('rut'))
                razon_social = limpiar_caracteres_especiales(row.get('razon_social') or "")
                giro = limpiar_caracteres_especiales(row.get('giro') or "Particular")
            
            giro = giro[:40]
            
            precio_cli = row.get('precio_cliente') or 0
            costo_desp = row.get('costo_despacho') or 0
            precio = precio_cli + costo_desp
            
            # --- CAMBIO IMPORTANTE AQUÍ ---
            # Intentamos sacar fecha_entrega, si no existe, usamos fecha_compra como respaldo
            f_obj = row.get('fecha_entrega') or row.get('fecha_compra')
            fecha = f_obj.strftime('%d/%m/%Y') if f_obj else ""
            # ------------------------------
            
            dir_raw = row.get('direccion') or ""
            direccion_limpia = limpiar_caracteres_especiales(dir_raw)
            direccion_truncada = direccion_limpia[:60]
            
            fila_nubox = [
                tipo,
                folio_orden,
                secuencia,
                fecha, # Ahora sí trae la fecha correcta
                rut,
                razon_social,
                giro,
                limpiar_caracteres_especiales(row.get('comuna') or ""),
                direccion_truncada,
                "SI",
                limpiar_caracteres_especiales(producto),
                numero_orden,
                row.get('unidades') or 1,
                precio,
                "0",
                limpiar_caracteres_especiales(row.get('email') or ""),
                "3",
                "", "", ""
            ]
            
            resultado.append(fila_nubox)
    
    return resultado

@router.get("/productos")
async def obtener_productos():
    """Obtener lista de productos para dropdown"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
        SELECT id, sku, nombre, precio_venta 
        FROM productos 
        WHERE sku IS NOT NULL AND nombre IS NOT NULL
        ORDER BY nombre
        """
        
        cursor.execute(query)
        productos = cursor.fetchall()
        
        return productos
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener productos: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/manual/guardar", response_model=VentaManualResponse)
async def guardar_venta_manual(venta_data: VentaManualRequest):
    """Guardar venta manual con múltiples productos"""
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    try:
        ventas_creadas = 0
        
        for producto_item in venta_data.productos:
            # Crear una venta por cada unidad del producto
            for i in range(producto_item.cantidad):
                # Definir columnas exactamente como están en la base de datos
                columnas = [
                    "cliente_id", "numero_orden", "cliente_final", "rut_documento", "email",
                    "telefono", "fecha_entrega", "fecha_cliente", "producto", "precio",
                    "precio_cliente", "costo_despacho", "comuna", "direccion", "region",
                    "sku", "estado", "documento", "razon_social", "rut", "giro",
                    "direccion_factura", "courier", "unidades", "users_id", "fecha_compra"
                ]
                
                # Obtener valores, usando valores por defecto para campos opcionales
                valores = [
                    venta_data.cliente_id,
                    f"{venta_data.numero_orden}-{ventas_creadas + 1:03d}",
                    "",  # cliente_final
                    "",  # rut_documento
                    "",  # email
                    "",  # telefono
                    producto_item.fecha_entrega,
                    venta_data.fecha_compra,
                    producto_item.producto,
                    0,   # precio
                    0,   # precio_cliente
                    0,   # costo_despacho
                    "",  # comuna
                    "",  # direccion
                    "",  # region
                    "",  # sku
                    "nueva",  # estado
                    "boleta",  # documento
                    "",  # razon_social
                    "",  # rut
                    "Particular",  # giro
                    "",  # direccion_factura
                    "Retiro en tienda",  # courier
                    1,   # unidades
                    1,   # users_id
                    venta_data.fecha_compra
                ]

                placeholders = ", ".join(["%s"] * len(columnas))
                columnas_str = ", ".join(columnas)

                query = f"""
                    INSERT INTO ventas_retail ({columnas_str})
                    VALUES ({placeholders})
                """
                
                cursor.execute(query, valores)
                ventas_creadas += 1
        
        conn.commit()
        
        return VentaManualResponse(
            mensaje=f"Se crearon {ventas_creadas} ventas exitosamente",
            ventas_creadas=ventas_creadas
        )
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Error al crear ventas: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def obtener_siguiente_dia_habil(fecha):
    """Suma días a una fecha saltando Sábados (5) y Domingos (6)"""
    # weekday() -> 0: Lunes, 1: Martes, ..., 5: Sábado, 6: Domingo
    if fecha.weekday() == 5: # Si es Sábado
        return fecha + timedelta(days=2) # Pasa a Lunes
    if fecha.weekday() == 6: # Si es Domingo
        return fecha + timedelta(days=1) # Pasa a Lunes
    return fecha

@router.get("/manifiesto/imprimir", response_class=HTMLResponse)
async def vista_imprimir_manifiesto(request: Request):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    
    hoy = datetime.now().date()
    
    # CALCULAMOS LOS 2 SIGUIENTES DÍAS HÁBILES
    # Día 1 hábil (Mañana o Lunes si hoy es viernes)
    dia_habil_1 = obtener_siguiente_dia_habil(hoy + timedelta(days=1))
    
    # Día 2 hábil (Pasado mañana o Martes si hoy es viernes)
    dia_habil_2 = obtener_siguiente_dia_habil(dia_habil_1 + timedelta(days=1))
    
    try:
        # La query ahora busca todo lo menor o igual al segundo día hábil
        query = """
            SELECT c.nombre AS cliente, vr.fecha_entrega, vr.numero_orden, 
                   vr.producto, vr.courier
            FROM ventas_retail vr
            JOIN clientes c ON vr.cliente_id = c.id
            WHERE vr.estado = 'nueva' AND vr.fecha_entrega <= %s
            ORDER BY vr.fecha_entrega ASC, vr.courier ASC
        """
        cursor.execute(query, (dia_habil_2,))
        ventas_raw = cursor.fetchall()

        ventas_procesadas = []
        for v in ventas_raw:
            fecha_v = v['fecha_entrega']
            if isinstance(fecha_v, datetime): fecha_v = fecha_v.date()
            
            dias_num = (hoy - fecha_v).days
            
            # LÓGICA DE ETIQUETAS DINÁMICAS
            if fecha_v < hoy:
                etiqueta = f"{dias_num}d"
            elif fecha_v == hoy:
                etiqueta = "Hoy"
            elif fecha_v == dia_habil_1:
                # Si dia_habil_1 es Lunes pero hoy es Viernes, dirá "Lunes"
                etiqueta = "Mañana" if (dia_habil_1 - hoy).days == 1 else dia_habil_1.strftime('%A').capitalize()
            elif fecha_v == dia_habil_2:
                etiqueta = "P. Mañana" if (dia_habil_2 - hoy).days <= 2 else dia_habil_2.strftime('%A').capitalize()
            else:
                etiqueta = fecha_v.strftime('%d-%m')

            # Traducción simple de días si no usas locales en español
            dias_esp = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", 
                        "Thursday": "Jueves", "Friday": "Viernes"}
            for eng, esp in dias_esp.items():
                etiqueta = etiqueta.replace(eng, esp)

            ventas_procesadas.append({
                "cliente": v['cliente'],
                "fecha_entrega": fecha_v.strftime('%d-%m-%Y'),
                "numero_orden": v['numero_orden'],
                "producto": v['producto'],
                "courier": v['courier'] or "Por asignar",
                "dias_atraso": etiqueta,
                "es_alerta": fecha_v <= hoy
            })

        return templates.TemplateResponse("ventas/manifiesto_print.html", {
            "request": request,
            "ventas": ventas_procesadas,
            "hoy": hoy.strftime('%d-%m-%Y')
        })
    finally:
        cursor.close()
        conn.close()