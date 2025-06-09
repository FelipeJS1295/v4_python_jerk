from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from db import conectar_mysql
import difflib
import re
from collections import defaultdict
from datetime import datetime

router = APIRouter(prefix="/ventas", tags=["Ventas"])

COLORES_COMUNES = [
    "Gris Oscuro", "Gris Perla", "Chocolate", "Beige", "Burdeo", "Terracota",
    "Negro", "Negra", "Blanco", "Rojo", "Azul", "Lino Gris Oscuro"
]

def extraer_tipo(nombre):
    nombre = nombre.lower()
    if "seccional" in nombre:
        return "Seccional"
    elif "poltrona" in nombre:
        return "Poltrona"
    elif "sofa" in nombre or "sofá" in nombre:
        return "Sofá"
    elif "cojín" in nombre:
        return "Cojín"
    else:
        return "Otro"

def extraer_color(nombre):
    nombre = nombre.lower()
    for color in COLORES_COMUNES:
        palabras = color.lower().split()
        if all(p in nombre for p in palabras):
            return color
    return ""

def obtener_base(nombre, tipo, color):
    nombre = nombre.lower().replace(tipo.lower(), "").replace(color.lower(), "")
    nombre = re.sub(r"[^a-záéíóúüñ 0-9]", "", nombre)
    return nombre.strip()

def agrupar_productos_nombres(nombres):
    grupos = []
    usados = set()
    for i, nombre in enumerate(nombres):
        if nombre in usados:
            continue
        tipo_i = extraer_tipo(nombre)
        color_i = extraer_color(nombre)
        base_i = obtener_base(nombre, tipo_i, color_i)
        grupo_actual = [nombre]
        usados.add(nombre)
        for j in range(i+1, len(nombres)):
            nombre_j = nombres[j]
            if nombre_j in usados:
                continue
            tipo_j = extraer_tipo(nombre_j)
            color_j = extraer_color(nombre_j)
            if tipo_i == tipo_j and color_i == color_j:
                base_j = obtener_base(nombre_j, tipo_j, color_j)
                ratio = difflib.SequenceMatcher(None, base_i, base_j).ratio()
                if ratio > 0.7:
                    grupo_actual.append(nombre_j)
                    usados.add(nombre_j)
        if grupo_actual:
            grupos.append(grupo_actual)
    return grupos

def construir_mapeo(grupos):
    mapeo = {}
    for grupo in grupos:
        if len(grupo) <= 1:
            continue
        base = min(grupo, key=len)
        for nombre in grupo:
            mapeo[nombre] = base
    return mapeo

@router.get("/maestra", response_class=JSONResponse)
def obtener_maestra(cliente_id: int = Query(None), fecha_inicio: str = Query(None), fecha_fin: str = Query(None)):
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT vr.cliente_id, c.nombre AS cliente, vr.fecha_entrega, vr.producto, SUM(vr.unidades) as unidades
        FROM ventas_retail vr
        JOIN clientes c ON c.id = vr.cliente_id
        WHERE 1
    """
    params = []

    if cliente_id:
        query += " AND vr.cliente_id = %s"
        params.append(cliente_id)

    if fecha_inicio:
        query += " AND vr.fecha_entrega >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        query += " AND vr.fecha_entrega <= %s"
        params.append(fecha_fin)

    query += " GROUP BY vr.cliente_id, c.nombre, vr.fecha_entrega, vr.producto"

    cursor.execute(query, params)
    resultados = cursor.fetchall()

    # Construir estructura
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    productos_todos = set()
    fechas = set()
    totales_por_fecha = defaultdict(int)
    total_general = 0

    for fila in resultados:
        cliente = fila['cliente']
        producto = fila['producto']
        fecha_raw = fila['fecha_entrega']

        if isinstance(fecha_raw, datetime):
            fecha = fecha_raw.strftime('%d-%m-%Y')
        else:
            fecha = str(fecha_raw)

        unidades = fila['unidades']

        data[cliente][producto][fecha] += unidades
        productos_todos.add(producto)
        fechas.add(fecha)

        totales_por_fecha[fecha] += unidades
        total_general += unidades

    return {
        "datos": data,
        "fechas": sorted(fechas),
        "totales_por_fecha": dict(totales_por_fecha),
        "total_general": total_general
    }
