import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List, Dict
from utils.hites_csv import procesar_archivos_hites
from db import conectar_mysql

router = APIRouter(prefix="/ventas", tags=["Ventas Retail Hites"])

@router.post("/importar-hites/")
async def importar_hites(
    archivo_ordenes: UploadFile = File(...),
    archivo_detalles: UploadFile = File(...)
):
    if not (archivo_ordenes.filename.endswith(('.csv', '.txt')) and 
            archivo_detalles.filename.endswith(('.csv', '.txt'))):
        raise HTTPException(status_code=400, detail="Ambos archivos deben ser CSV o TXT")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp1:
            temp1.write(await archivo_ordenes.read())
            path_ordenes = temp1.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp2:
            temp2.write(await archivo_detalles.read())
            path_detalles = temp2.name

        ventas = procesar_archivos_hites(path_ordenes, path_detalles)

        os.remove(path_ordenes)
        os.remove(path_detalles)

        return ventas

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/importar-hites/guardar")
async def guardar_ventas_hites(ventas: List[Dict] = Body(...)):
    try:
        conn = conectar_mysql()
        cursor = conn.cursor()
        insertadas = 0

        for venta in ventas:
            if venta.get("ya_existe"):
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
