"""
==============================================================================
CELERY WORKER (celery_worker.py)
Punto de entrada y configuración del motor de colas local
==============================================================================
"""

import os
from celery import Celery
from dotenv import load_dotenv

# 🛡️ 1. ¡PRIMERO cargamos las contraseñas del archivo .env!
load_dotenv(override=True)

# 🛡️ 2. Leemos la URL de Redis (El Puente)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# EL DNI DEL BOT LOCAL
MI_USER_ID = os.getenv("MI_USER_ID", "1")
MI_COLA = f"cola_usuario_{MI_USER_ID}"

print("="*50)
print(f"🤖 INICIANDO BOT LOCAL PARA EL USUARIO ID: {MI_USER_ID}")
print(f"📡 Escuchando órdenes exclusivamente en: {MI_COLA}")
print("="*50)

# 🛡️ 3. FINALMENTE, arrancamos el motor de Celery
celery = Celery(
    "aintelligence_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['services.tasks'] # Celery ya importa el archivo con esto, no hace falta import manual
)

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    task_default_queue=MI_COLA,  # <-- ¡El enrutado exclusivo!
)