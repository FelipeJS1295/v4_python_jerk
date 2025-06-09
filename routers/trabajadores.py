from fastapi import APIRouter
from db import conectar_mysql

router = APIRouter(prefix="/trabajadores", tags=["Trabajadores"])

@router.get("/")
def listar_trabajadores():
    conn = conectar_mysql()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombres FROM trabajadores")
    resultado = cursor.fetchall()
    cursor.close()
    conn.close()
    return resultado
