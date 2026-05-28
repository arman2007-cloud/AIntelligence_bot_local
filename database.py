"""
==============================================================================
DATABASE API CLIENT (database.py)
Conexión segura entre el Bot Local y el Servidor Web (Nube)
==============================================================================
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "")

# 🛡️ El "Carnet VIP" que abre las puertas del backend web
HEADERS = {"X-Worker-Key": WORKER_API_KEY}

def save_lead(lead_dict: dict, user_id: int):
    try:
        payload = {"lead": lead_dict, "user_id": user_id}
        requests.post(f"{API_BASE_URL}/leads", json=payload, headers=HEADERS, timeout=15)
    except Exception as e:
        logger.error(f"Error enviando lead a la nube: {e}")

def update_lead_status(url: str, status: str, user_id: int):
    try:
        payload = {"url": url, "status": status, "user_id": user_id}
        requests.put(f"{API_BASE_URL}/leads/status", json=payload, headers=HEADERS, timeout=15)
    except Exception as e:
        logger.warning(f"No se pudo actualizar estado en la nube: {e}")

def log_activity(action_type: str, url: str, success: bool, user_id: int):
    try:
        payload = {"action_type": action_type, "url": url, "success": success, "user_id": user_id}
        requests.post(f"{API_BASE_URL}/activity", json=payload, headers=HEADERS, timeout=15)
    except Exception as e:
        logger.warning(f"No se pudo registrar actividad en la nube: {e}")

def get_daily_count(action_type: str, user_id: int) -> int:
    try:
        res = requests.get(f"{API_BASE_URL}/limits/daily", params={"action_type": action_type, "user_id": user_id}, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json().get("count", 0)
    except Exception as e:
        logger.warning(f"Fallo al leer límite diario de la nube: {e}")
    return 0

def get_favorite_companies(user_id: int) -> list:
    try:
        res = requests.get(f"{API_BASE_URL}/favorites", params={"user_id": user_id}, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return res.json().get("favorites", [])
    except Exception as e:
        logger.warning(f"Fallo al leer favoritos de la nube: {e}")
    return []