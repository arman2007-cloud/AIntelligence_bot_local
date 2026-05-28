import os
import time
import requests
from functools import wraps
from config import MALTA_LOCATIONS, MALTA_SECTORS, SENIOR_KEYWORDS, JUNIOR_KEYWORDS

# ──────────────────────────────────────────────────────────────────────────────
# ALGORITMO DE PUNTUACIÓN (LEAD SCORING)
# ──────────────────────────────────────────────────────────────────────────────
def score_lead(profile: dict) -> int:
    """Analiza un perfil y le asigna una puntuación de 0 a 100."""
    text = " ".join([
        profile.get("job_title", ""),
        profile.get("company",   ""),
        profile.get("location",  ""),
        profile.get("name",      ""),
    ]).lower()

    score = 0

    if any(loc.lower() in text for loc in MALTA_LOCATIONS):
        score += 40
    if any(sector.lower() in text for sector in MALTA_SECTORS):
        score += 30
    if any(kw in text for kw in SENIOR_KEYWORDS):
        score += 20
    if any(kw in text for kw in JUNIOR_KEYWORDS):
        score -= 10

    return max(0, min(100, score))

# ──────────────────────────────────────────────────────────────────────────────
# RESILIENCIA EMPRESARIAL (REINTENTOS DE RED)
# ──────────────────────────────────────────────────────────────────────────────
def with_retry(max_attempts=3, base_delay=5.0, backoff=2.0):
    """Decorador de backoff exponencial para evitar caídas por micro-cortes de red."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.Timeout, requests.ConnectionError, requests.exceptions.RequestException) as e:
                    last_error = e
                    if attempt < max_attempts:
                        wait = base_delay * (backoff ** (attempt - 1))
                        print(f"⚠️ [Intento {attempt}/{max_attempts}] Fallo de red. Reintentando en {wait:.1f}s...")
                        time.sleep(wait)
                    else:
                        print(f"❌ Error crítico: Imposible conectar tras {max_attempts} intentos.")
                        raise RuntimeError(f"Fallo de red persistente: {last_error}") from e
        return wrapper
    return decorator

@with_retry(max_attempts=3, base_delay=4.0)
def call_n8n_safely(url: str, payload: dict, timeout: int = 120) -> dict:
    """
    Llama a N8N de forma segura usando POST y autenticación por cabecera.
    """
    # Leemos la contraseña del entorno, nunca del código duro
    n8n_key = os.getenv("N8N_API_KEY")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    if n8n_key:
        headers["X-N8N-Key"] = n8n_key
        
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    
    # 🛡️ Si Plesk nos bloquea (403/500), forzamos que salte al bloque except para no quedarnos ciegos
    response.raise_for_status()
    
    # 📸 LA CÁMARA DE SEGURIDAD: Imprimimos el texto exacto que envía el servidor
    print(f"\n📦 RESPUESTA CRUDA DE N8N:\n{response.text}\n")
    
    return response.json()