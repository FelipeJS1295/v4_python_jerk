from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import threading
from typing import Dict, List
import logging
import os

# Configurar templates (usando la misma estructura de tu proyecto)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter(prefix="/camaras", tags=["camaras"])

# Configuración de las cámaras de JERKHOME DVR (luego esto vendrá de la base de datos)
CAMARAS_CONFIG = {
    "1": {
        "id": "1",
        "nombre": "Cámara 1",
        "ubicacion": "Entrada Principal",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1&unicast=true&proto=Onvif",
        "activa": True
    },
    "2": {
        "id": "2", 
        "nombre": "Cámara 2",
        "ubicacion": "Patio Trasero",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=2&subtype=1&unicast=true&proto=Onvif",
        "activa": True
    },
    "4": {
        "id": "4",
        "nombre": "Cámara 4", 
        "ubicacion": "Bodega",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=4&subtype=1&unicast=true&proto=Onvif",
        "activa": True
    },
    "5": {
        "id": "5",
        "nombre": "Cámara 5",
        "ubicacion": "Oficina",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=5&subtype=1&unicast=true&proto=Onvif", 
        "activa": True
    },
    "6": {
        "id": "6",
        "nombre": "Cámara 6",
        "ubicacion": "Pasillo",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=6&subtype=1&unicast=true&proto=Onvif",
        "activa": True
    },
    "8": {
        "id": "8",
        "nombre": "Cámara 8", 
        "ubicacion": "Estacionamiento",
        "rtsp_url": "rtsp://admin:MEMO2812@192.168.1.108:554/cam/realmonitor?channel=8&subtype=1&unicast=true&proto=Onvif",
        "activa": True
    }
}

# Variable global para tracking de streams
streams_activos = {}

@router.get("/")
async def dashboard_camaras(request: Request):
    """Dashboard principal de cámaras - Protegido por middleware de autenticación"""
    usuario = getattr(request.state, 'usuario', None)
    
    # Obtener lista de cámaras activas
    camaras_activas = {k: v for k, v in CAMARAS_CONFIG.items() if v["activa"]}
    
    return templates.TemplateResponse("camaras/dashboard.html", {
        "request": request,
        "usuario": usuario,
        "camaras": camaras_activas
    })

@router.get("/lista")
async def obtener_lista_camaras():
    """API endpoint para obtener lista de cámaras"""
    try:
        camaras_activas = [
            {
                "id": camara["id"],
                "nombre": camara["nombre"],
                "ubicacion": camara["ubicacion"],
                "activa": camara["activa"]
            }
            for camara in CAMARAS_CONFIG.values() if camara["activa"]
        ]
        
        return {
            "success": True,
            "camaras": camaras_activas,
            "total": len(camaras_activas)
        }
    except Exception as e:
        logging.error(f"Error obteniendo lista de cámaras: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/{camera_id}")
async def stream_camara(camera_id: str, request: Request):
    """Endpoint para streaming de cámara específica"""
    try:
        # Verificar que la cámara existe y está activa
        if camera_id not in CAMARAS_CONFIG:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        
        if not CAMARAS_CONFIG[camera_id]["activa"]:
            raise HTTPException(status_code=400, detail="Cámara no activa")
        
        # Verificar autenticación (el middleware ya lo hizo, pero por seguridad)
        usuario = getattr(request.state, 'usuario', None)
        if not usuario:
            raise HTTPException(status_code=401, detail="No autorizado")
        
        # Por ahora, intentemos importar cv2 aquí para ver el error específico
        try:
            import cv2
            
            # Gestor simple de streaming
            def generar_stream():
                try:
                    rtsp_url = CAMARAS_CONFIG[camera_id]["rtsp_url"]
                    cap = cv2.VideoCapture(rtsp_url)
                    
                    # Configurar parámetros básicos
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    cap.set(cv2.CAP_PROP_FPS, 25)
                    
                    if not cap.isOpened():
                        raise ValueError(f"No se pudo conectar a la cámara {camera_id}")
                    
                    streams_activos[camera_id] = True
                    
                    while streams_activos.get(camera_id, False):
                        ret, frame = cap.read()
                        if not ret:
                            logging.warning(f"Error leyendo frame de cámara {camera_id}")
                            break
                        
                        # Redimensionar frame para optimizar ancho de banda
                        height, width = frame.shape[:2]
                        if width > 800:
                            scale = 800 / width
                            new_width = int(width * scale)
                            new_height = int(height * scale)
                            frame = cv2.resize(frame, (new_width, new_height))
                        
                        # Codificar como JPEG
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        frame_bytes = buffer.tobytes()
                        
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                        
                except Exception as e:
                    logging.error(f"Error en stream de cámara {camera_id}: {e}")
                    streams_activos[camera_id] = False
                finally:
                    if 'cap' in locals():
                        cap.release()
                    streams_activos[camera_id] = False
            
            return StreamingResponse(
                generar_stream(),
                media_type="multipart/x-mixed-replace;boundary=frame"
            )
            
        except ImportError as e:
            # OpenCV no está instalado
            return JSONResponse(
                status_code=500, 
                content={
                    "error": "OpenCV no está instalado",
                    "mensaje": "Ejecuta: pip install opencv-python-headless",
                    "detalle": str(e)
                }
            )
        
    except Exception as e:
        logging.error(f"Error en stream de cámara {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/{camera_id}/detener")
async def detener_stream_camara(camera_id: str):
    """Detiene el stream de una cámara específica"""
    try:
        if camera_id not in CAMARAS_CONFIG:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        
        streams_activos[camera_id] = False
        
        return {
            "success": True,
            "message": f"Stream de cámara {camera_id} detenido"
        }
        
    except Exception as e:
        logging.error(f"Error deteniendo stream de cámara {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{camera_id}")
async def obtener_status_camara(camera_id: str):
    """Obtiene el status de una cámara específica"""
    try:
        if camera_id not in CAMARAS_CONFIG:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        
        camera_config = CAMARAS_CONFIG[camera_id]
        stream_activo = streams_activos.get(camera_id, False)
        
        return {
            "success": True,
            "camera_id": camera_id,
            "nombre": camera_config["nombre"],
            "ubicacion": camera_config["ubicacion"],
            "activa": camera_config["activa"],
            "stream_activo": stream_activo,
            "opencv_disponible": self.verificar_opencv()
        }
        
    except Exception as e:
        logging.error(f"Error obteniendo status de cámara {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-conexion/{camera_id}")
async def test_conexion_camara(camera_id: str):
    """Prueba la conexión a una cámara específica"""
    try:
        if camera_id not in CAMARAS_CONFIG:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")
        
        # Verificar OpenCV
        try:
            import cv2
        except ImportError:
            return {
                "success": False,
                "message": "OpenCV no está instalado. Ejecuta: pip install opencv-python-headless"
            }
        
        # Intentar conexión básica
        rtsp_url = CAMARAS_CONFIG[camera_id]["rtsp_url"]
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            cap.release()
            return {
                "success": False,
                "message": f"No se pudo conectar a {rtsp_url}"
            }
        
        # Intentar leer un frame
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            return {
                "success": True,
                "message": "Conexión exitosa",
                "frame_size": f"{frame.shape[1]}x{frame.shape[0]}"
            }
        else:
            return {
                "success": False, 
                "message": "Conexión establecida pero no se pudo leer frame"
            }
            
    except Exception as e:
        logging.error(f"Error probando conexión de cámara {camera_id}: {e}")
        return {
            "success": False,
            "message": f"Error de conexión: {str(e)}"
        }

@router.post("/test-urls")
async def test_todas_urls():
    """Prueba todas las URLs RTSP configuradas"""
    try:
        # Verificar OpenCV
        try:
            import cv2
        except ImportError:
            return {
                "success": False,
                "message": "OpenCV no está instalado. Ejecuta: pip install opencv-python-headless"
            }
        
        resultados = {}
        
        for camera_id, config in CAMARAS_CONFIG.items():
            rtsp_url = config["rtsp_url"]
            
            # Intentar conexión
            cap = cv2.VideoCapture(rtsp_url)
            
            if not cap.isOpened():
                resultados[camera_id] = {
                    "success": False,
                    "nombre": config["nombre"],
                    "ubicacion": config["ubicacion"],
                    "message": "No se pudo conectar",
                    "url": rtsp_url
                }
            else:
                # Intentar leer un frame
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    resultados[camera_id] = {
                        "success": True,
                        "nombre": config["nombre"],
                        "ubicacion": config["ubicacion"],
                        "message": "Conexión exitosa",
                        "frame_size": f"{frame.shape[1]}x{frame.shape[0]}",
                        "url": rtsp_url
                    }
                else:
                    resultados[camera_id] = {
                        "success": False,
                        "nombre": config["nombre"],
                        "ubicacion": config["ubicacion"],
                        "message": "Conecta pero no lee frames",
                        "url": rtsp_url
                    }
            
            cap.release()
        
        # Resumen
        exitosas = len([r for r in resultados.values() if r["success"]])
        total = len(resultados)
        
        return {
            "success": exitosas > 0,
            "resumen": f"{exitosas}/{total} cámaras conectaron exitosamente",
            "resultados": resultados,
            "dvr_info": {
                "dispositivo": "JERKHOME",
                "ip": "192.168.1.108",
                "usuario": "admin",
                "puerto_rtsp": 554
            }
        }
        
    except Exception as e:
        logging.error(f"Error probando URLs RTSP: {e}")
        return {
            "success": False,
            "message": f"Error general: {str(e)}"
        }

@router.get("/configuracion")
async def obtener_configuracion():
    """Obtiene la configuración actual del sistema de cámaras"""
    return {
        "dvr_info": {
            "dispositivo": "JERKHOME",
            "ip": "192.168.1.108", 
            "usuario": "admin",
            "puerto_rtsp": 554,
            "modelo": "DHI-XVR5108HS-4KL"
        },
        "camaras": [
            {
                "id": config["id"],
                "nombre": config["nombre"],
                "ubicacion": config["ubicacion"],
                "activa": config["activa"],
                "canal": config["id"]
            }
            for config in CAMARAS_CONFIG.values()
        ],
        "total_camaras": len(CAMARAS_CONFIG),
        "camaras_activas": len([c for c in CAMARAS_CONFIG.values() if c["activa"]])
    }

def verificar_opencv():
    """Función auxiliar para verificar si OpenCV está disponible"""
    try:
        import cv2
        return True
    except ImportError:
        return False