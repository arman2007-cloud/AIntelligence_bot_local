import os
import requests
import logging

logger = logging.getLogger(__name__)

# Configuraciones de conexión al Cerebro (Nube)
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "")

# El "Carnet VIP" que abre las puertas del backend web
HEADERS = {"X-Worker-Key": WORKER_API_KEY}

def update_task(task_id: str, **kwargs):
    """Llama a la web para decirle cómo va el porcentaje de la barra de progreso"""
    try:
        # 🛡️ FIX 1: Cambiamos PATCH por POST y añadimos /update a la ruta para evitar bloqueos de Plesk (WAF)
        res = requests.post(f"{API_BASE_URL}/tasks/{task_id}/update", json=kwargs, headers=HEADERS, timeout=15)
        
        # 🛡️ FIX 2: ¡El bot recupera la vista! Si Plesk da un error 403 o 500, esto forzará que salte al except.
        res.raise_for_status() 
    except Exception as e:
        logger.error(f"Error actualizando tarea {task_id} en la nube: {e}")

def get_task(task_id: str, user_id: int = None) -> dict:
    """Llama a la web (Walkie-Talkie) para preguntar si el usuario ha pulsado Pause o Stop"""
    try:
        params = {"user_id": user_id} if user_id else {}
        res = requests.get(f"{API_BASE_URL}/tasks/{task_id}", params=params, headers=HEADERS, timeout=15)
        
        # 🛡️ FIX 3: Evitamos el bug de "velocidad de la luz" asegurándonos de que no devuelva None si hay error.
        res.raise_for_status()
        
        if res.status_code == 200:
            return res.json().get("task")
    except Exception as e:
        logger.error(f"Error obteniendo estado de tarea {task_id}: {e}")
    return None