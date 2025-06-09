import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List, Dict
from utils.ripley_csv import procesar_csv_ripley
from db import conectar_mysql

router = APIRouter(prefix="/ventas", tags=["Ventas Retail Ripley"])

@router.post("/importar-ripley/")
async def importar_ripley(archivo: UploadFile = File(...)):
    if not archivo.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser CSV (.csv)")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            temp_file.write(await archivo.read())
            temp_path = temp_file.name

        ventas = procesar_csv_ripley(temp_path)
        os.remove(temp_path)
        return ventas

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/importar-ripley/guardar")
async def guardar_ventas_ripley(ventas: List[Dict] = Body(...)):
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
