from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from db import conectar_mysql
from datetime import datetime

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

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
        print("❌ ERROR en /dashboard/totales:", e)
        raise HTTPException(status_code=500, detail="Error interno en el servidor.")
    finally:
        conn.close()

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
            print("👉 Fila:", row)  # 👈 IMPRIME CADA FILA PARA DEBUG

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

        print("✅ Totales:", total_unidades, total_vendido, total_neto)

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

