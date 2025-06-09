import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import List, Dict
from utils.walmart_excel import procesar_excel_walmart
from db import conectar_mysql

router = APIRouter(prefix="/ventas", tags=["Ventas Retail Walmart"])

@router.post("/importar-walmart/")
async def importar_excel_walmart(archivo: UploadFile = File(...)):
    if not archivo.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xlsx o .xls")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp:
            temp.write(await archivo.read())
            temp_path = temp.name

        ventas = procesar_excel_walmart(temp_path)
        os.remove(temp_path)
        return ventas

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/importar-walmart/guardar")
async def guardar_ventas_walmart(ventas: List[Dict] = Body(...)):
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        insertadas = 0

        for venta in ventas:
            if venta.get("ya_existe") is True:
                continue

            columnas = []
            valores = []
            for k, v in venta.items():
                if k != "ya_existe":
                    columnas.append(k)
                    valores.append(v)

            campos_sql = ", ".join(columnas)
            placeholders = ", ".join(["%s"] * len(valores))

            query = f"INSERT INTO ventas_retail ({campos_sql}) VALUES ({placeholders})"
            cursor.execute(query, valores)
            insertadas += 1

        conn.commit()
        cursor.close()
        conn.close()

        return {"mensaje": f"{insertadas} ventas insertadas correctamente"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
