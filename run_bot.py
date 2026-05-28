import multiprocessing
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from celery_worker import celery

def arrancar_programa():
    id_actual = os.getenv("MI_USER_ID", "1")
    
    print("=" * 50)
    print(f"INICIANDO BOT LOCAL PARA EL USUARIO ID: {id_actual}")
    print(f"Escuchando órdenes exclusivamente en: cola_usuario_{id_actual}")
    print("=" * 50)
    print("Por favor, no cierres esta ventana mientras trabajas en la web.\n")
    
    argumentos_celery = [
        'worker', 
        '--loglevel=info', 
        f'--queues=cola_usuario_{id_actual}', 
        '--pool=solo'
    ]
    
    celery.worker_main(argumentos_celery)

if __name__ == '__main__':

    multiprocessing.freeze_support()
    arrancar_programa()