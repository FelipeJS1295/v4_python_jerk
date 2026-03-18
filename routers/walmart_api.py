import datetime

@router.get("/test-orders")
async def probar_ordenes():
    # 1. Obtener el token
    token = walmart_api.obtener_token()
    if not token:
        return {"error": "No se pudo obtener el token. Revisa tus credenciales en el .env"}

    # 2. Configurar la fecha (últimos 7 días)
    # Walmart usa formato ISO 8601 (YYYY-MM-DDTHH:mm:ssZ)
    hace_7_dias = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')

    # 3. Preparar la llamada a la API de Órdenes
    url = "https://marketplace.walmartapis.com/v3/orders"
    headers = {
        "WM_SEC.ACCESS_TOKEN": token,
        "Authorization": f"Basic {walmart_api.get_basic_auth()}", # Necesitaremos esta pequeña función en el service
        "WM_SVC.NAME": "Walmart Marketplace",
        "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
        "WM_MARKET": "cl",
        "Accept": "application/json"
    }
    
    params = {"createdStartDate": hace_7_dias}

    try:
        response = requests.get(url, headers=headers, params=params)
        return response.json() # Esto mostrará el JSON crudo en tu pantalla
    except Exception as e:
        return {"error": str(e)}