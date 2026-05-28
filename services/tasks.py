# services/tasks.py
import json
import re
import requests
import csv
import io
import time
import random
import os
import traceback  
import logging    
from difflib import SequenceMatcher
from dotenv import load_dotenv

from celery_worker import celery
from task_manager import update_task, get_task
from database import save_lead, get_favorite_companies, get_daily_count
from lead_schema import CandidateSchema
from services.linkedin_bot import get_driver, process_profile, safe_sleep, esperar_inicio_sesion
from ai_agent import redactar_mensaje_conexion
from utils import call_n8n_safely, score_lead
from drive_export import export_and_upload

logger = logging.getLogger(__name__)
load_dotenv(override=True)

MAX_DAILY_LIMIT = int(os.getenv("MAX_CONEXIONES", 25))

def escuchar_ordenes_nube(task_id: str):
    """EL WALKIE-TALKIE: Escucha interrupciones de la base de datos."""
    while True:
        tarea = get_task(task_id)
        if not tarea:
            break
        if tarea['status'] == 'CANCELED':
            raise InterruptedError("🛑 Tarea cancelada por el usuario desde la web.")
        if tarea['status'] == 'PAUSED':
            time.sleep(5)
            continue 
        break

def is_favorite_company(company_name, favorites_list):
    if not company_name or company_name.lower() in ["confidencial", "not specified"]: return False
    def clean(n): return re.sub(r'[^a-zA-Z0-9 ]', '', re.sub(r'(?i)\b(ltd|inc|llc|corp|group|s\.l\.|s\.a\.|co|limited)\b', '', n)).strip().lower()
    c_clean = clean(company_name)
    if not c_clean: return False
    for fav in favorites_list:
        f_clean = clean(fav)
        if not f_clean: continue
        if f_clean in c_clean or c_clean in f_clean: return True
        if SequenceMatcher(None, c_clean, f_clean).ratio() > 0.85: return True
    return False

def extraer_json_ia(res_json):
    """🛡️ EL TRADUCTOR UNIVERSAL: Extrae la lista de candidatos limpiando el Markdown de Gemini."""
    
    # 🛡️ FIX: Si n8n devuelve null, lo atrapamos aquí con un mensaje claro
    if not res_json:
        logger.warning("⚠️ El cerebro (n8n) devolvió un paquete vacío (None/null). Revisa la configuración del nodo Webhook.")
        return []
        
    try:
        # Caso 0: Lista que contiene un diccionario con la clave 'resultados' (Dwayne Bug Fix)
        if isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict) and "resultados" in res_json[0]:
            if isinstance(res_json[0]["resultados"], list):
                return res_json[0]["resultados"]

        # Caso 1: Si ya es una lista directa de diccionarios con candidatos válida
        if isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict) and "name" in res_json[0]:
            return res_json
        
        # Caso 2: Si viene directamente dentro de un objeto/diccionario con la clave 'resultados'
        if isinstance(res_json, dict) and "resultados" in res_json:
            if isinstance(res_json["resultados"], list):
                return res_json["resultados"]
        
        # Caso 3: Si Gemini ha devuelto texto en bruto (dentro de las claves 'text', 'content' o 'output')
        texto_crudo = ""
        if isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict):
            texto_crudo = res_json[0].get("text", res_json[0].get("content", res_json[0].get("output", "")))
        elif isinstance(res_json, dict):
            texto_crudo = res_json.get("text", res_json.get("content", res_json.get("output", "")))
        
        if texto_crudo:
            # Exterminador de bloques Markdown de IA
            texto_limpio = re.sub(r'```json|```', '', texto_crudo).strip()
            parsed = json.loads(texto_limpio)
            if isinstance(parsed, dict) and "resultados" in parsed:
                return parsed["resultados"]
            return parsed if isinstance(parsed, list) else []
            
        logger.warning(f"⚠️ Formato de datos inesperado recibido desde n8n. RAW: {res_json}")
        return []
    except Exception as e:
        logger.error(f"❌ Fallo al parsear la respuesta de la IA: {e}")
        return []

@celery.task(bind=True)
def task_search_candidates(self, task_id, user_id, cargo, location, paginas):
    try:
        escuchar_ordenes_nube(task_id)
        update_task(task_id, progress=30, message="Iniciando conexión con la IA (n8n)...")
        
        webhook_url = os.getenv("N8N_WEBHOOK_URL")
        brutos = []
        
        for p in range(1, paginas + 1):
            update_task(task_id, message=f"Delegando búsqueda a n8n (Página {p}/{paginas})...")
            payload = {
                "action": "search_candidates", 
                "cargo": cargo, 
                "ubicacion": location,
                "page": p
            }
            res_json = call_n8n_safely(webhook_url, payload)
            
            nuevos_resultados = extraer_json_ia(res_json)

            if not nuevos_resultados:
                logger.warning(f"⚠️ No se obtuvieron candidatos útiles en la página {p}.")
                continue  # 🛡️ FIX: Usamos continue en lugar de break para no rendirnos si una página falla
                
            brutos.extend(nuevos_resultados)
            time.sleep(2) 
        
        all_results = []
        update_task(task_id, progress=70, message="Validando candidatos recibidos...")
        
        for idx, item in enumerate(brutos):
            escuchar_ordenes_nube(task_id) 
            try:
                score_final = item.get("score") or score_lead(item)
                
                cand = CandidateSchema(
                    name=item.get("name"), job_title=item.get("job_title", cargo), 
                    company=item.get("company"), location=item.get("location", location), 
                    url=item.get("url"), score=score_final
                )
                save_lead({
                    "url": cand.url, "name": cand.name, "job_title": cand.job_title, 
                    "company": cand.company, "score": cand.score, "source": "n8n Cloud", 
                    "location": cand.location
                }, user_id)
                all_results.append({
                    "id": idx, "name": cand.name, "score": cand.score, 
                    "meta": f"🛡️ Origen: n8n Cloud", "url": cand.url, 
                    "job_title": cand.job_title, "company": cand.company, "location": cand.location
                })
            except Exception as e: 
                logger.error(f"⚠️ Descartando candidato por error de validación técnica: {str(e)[:50]}")
                continue
        
        # 🚀 Exportar informe y sincronizar con HR Google Drive
        drive_link = ""
        try:
            update_task(task_id, message="Exportando reporte a HR Google Drive...")
            drive_link = export_and_upload(keyword=cargo, location=location, leads=all_results, mode="leads", log_fn=logger.info)
        except Exception as e:
            logger.error(f"Error en subida de candidatos a Google Drive: {e}")
            
        update_task(task_id, status='done', progress=100, message="Complete", result=json.dumps(all_results), drive_link=drive_link)
        
    except InterruptedError as e:
        update_task(task_id, status='error', error=str(e), message="Tarea detenida")
    except Exception as e: 
        logger.error(f"Error crítico en search_candidates: {e}")
        logger.error(traceback.format_exc())
        update_task(task_id, status='error', error=str(e), message="Error crítico.")

@celery.task(bind=True)
def task_search_jobs(self, task_id, user_id, cargo, location):
    try:
        escuchar_ordenes_nube(task_id)
        update_task(task_id, progress=20, message="Conectando al mercado (n8n)...")
        
        favs_db = get_favorite_companies(user_id)
        
        webhook_url = os.getenv("N8N_WEBHOOK_URL")
        payload = {"action": "search_jobs", "cargo": cargo, "ubicacion": location}
        res_json = call_n8n_safely(webhook_url, payload)
        
        vacantes = extraer_json_ia(res_json)
        
        all_res = []
        seen = set()
        update_task(task_id, progress=75, message="Cruzando con empresas favoritas...")
        
        for idx, item in enumerate(vacantes):
            escuchar_ordenes_nube(task_id) 
            url = str(item.get("url", ""))
            if not url or url in seen: continue
            seen.add(url)
            
            comp = item.get("company", "Confidencial")
            score_final = item.get("score") or score_lead(item)
            
            es_fav = is_favorite_company(comp, favs_db)
            if es_fav: score_final = 100
            
            all_res.append({
                "id": idx, "score": score_final, "company": comp, "job_title": item.get("job_title", "Oferta"), 
                "location": item.get("location", location), "url": url, "name": item.get("job_title"), 
                "meta": f"🏢 {comp} · 📍 {item.get('location')}", "is_favorite": es_fav
            })
            
        all_res.sort(key=lambda x: x['score'], reverse=True)
        
        # 🚀 Exportar informe y sincronizar con HR Google Drive
        drive_link = ""
        try:
            update_task(task_id, message="Exportando mercado a HR Google Drive...")
            drive_link = export_and_upload(keyword=cargo, location=location, leads=all_res, mode="jobs", log_fn=logger.info)
        except Exception as e:
            logger.error(f"Error en subida de ofertas de empleo a Google Drive: {e}")
            
        update_task(task_id, status='done', progress=100, message="Complete", result=json.dumps(all_res), drive_link=drive_link)
        
    except InterruptedError as e:
        update_task(task_id, status='error', error=str(e), message="Tarea detenida")
    except Exception as e: 
        logger.error(f"Error crítico en search_jobs: {e}")
        logger.error(traceback.format_exc())
        update_task(task_id, status='error', error=str(e), message="Error crítico.")

@celery.task(bind=True)
def task_run_outreach(self, task_id, user_id, selected_candidates, msg, cand_task_id=None):
    driver = None 
    try:
        driver = get_driver(user_id)
        if not driver:
            update_task(task_id, status='error', error="No se pudo iniciar Chrome.", message="Error en navegador")
            return

        c_task = get_task(cand_task_id, user_id=user_id) if cand_task_id else None
        cand_data = json.loads(c_task['result']) if c_task and c_task.get('result') else []

        for idx, name in enumerate(selected_candidates):
            escuchar_ordenes_nube(task_id)
            
            cand = next((c for c in cand_data if c['name'] == name), None)
            if not cand: continue
            
            update_task(task_id, status='running', message=f"Procesando candidato...", progress=int((idx/len(selected_candidates))*100))
            
            process_profile(driver, cand['url'], name, msg, user_id, cand.get('company'), cand.get('job_title'), task_id=task_id)
            
        update_task(task_id, status='done', progress=100, message="Outreach completado.")
        
    except InterruptedError as e:
        update_task(task_id, status='error', error=str(e), message="Tarea detenida")
    except Exception as e: 
        logger.error(f"Error crítico: {e}")
        update_task(task_id, status='error', error=str(e), message="Error crítico.")
    finally:
        if driver:
            try:
                driver.quit()
                from services.linkedin_bot import worker_drivers
                worker_drivers.pop(user_id, None)
            except Exception: pass

@celery.task(bind=True)
def task_run_manual_outreach(self, task_id, user_id, sheet_id, mensaje_base):
    driver = None 
    try:
        escuchar_ordenes_nube(task_id)
        update_task(task_id, status='running', message="Connecting to Google Sheets...")
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        res = requests.get(csv_url, timeout=30)
        
        if res.status_code != 200 or res.text.strip().lower().startswith('<!doctype html>'):
            raise Exception("Access Denied. Asegúrate de que el link es público.")
            
        res.encoding = 'utf-8'
        reader = csv.DictReader(io.StringIO(res.text))
        candidates = []
        
        for row in reader:
            row_lower = {k.strip().lower(): v for k, v in row.items() if k}
            name = row_lower.get('name', 'Candidate')
            url = row_lower.get('linkedin url', row_lower.get('url', ''))
            company = row_lower.get('company', row_lower.get('empresa', ''))
            job_title = row_lower.get('job title', row_lower.get('cargo', row_lower.get('title', '')))
            
            if url and 'linkedin.com' in url:
                candidates.append({"name": name.strip(), "url": url.strip(), "company": company.strip(), "job_title": job_title.strip()})
                
        if not candidates: raise Exception("No se encontraron URLs de LinkedIn.")

        user_invites_today = get_daily_count("connections", user_id)
        available = MAX_DAILY_LIMIT - user_invites_today
        if available <= 0: raise Exception("Daily limit reached.")
        if len(candidates) > available: candidates = candidates[:available]

        driver = get_driver(user_id)
        if not driver:
            update_task(task_id, status='error', error="No se pudo iniciar Chrome.", message="Error navegador")
            return

        for idx, cand in enumerate(candidates):
            escuchar_ordenes_nube(task_id)
            update_task(task_id, status='running', message=f"Processing candidato ({idx + 1}/{len(candidates)})...")
            process_profile(driver, cand['url'], cand['name'], mensaje_base, user_id, cand.get('company'), cand.get('job_title'), task_id=task_id)

        update_task(task_id, status='done', progress=100, message="✅ Manual outreach finished.")
        
    except InterruptedError as e: 
        update_task(task_id, status='error', error=str(e), message="Tarea detenida")
    except Exception as e: 
        logger.error(f"Error crítico: {e}")
        update_task(task_id, status='error', error=str(e), message="Error crítico.")
    finally:
        if driver:
            try:
                driver.quit()
                from services.linkedin_bot import worker_drivers
                worker_drivers.pop(user_id, None)
            except Exception: pass

@celery.task(bind=True)
def task_analyze_profile(self, task_id, user_id, url, name):
    try:
        escuchar_ordenes_nube(task_id)
        update_task(task_id, status='running', progress=20, message="Abriendo Chrome localmente...")
        
        driver = get_driver(user_id)
        if not driver:
            update_task(task_id, status='error', error="No se pudo iniciar Chrome.", message="Error navegador")
            return
            
        driver.get(url)
        safe_sleep(3, task_id=task_id)
        
        # 🛑 ACTIVAMOS EL CENTINELA AQUÍ TAMBIÉN
        esperar_inicio_sesion(driver, url_destino=url, task_id=task_id)
        
        # Una vez logueado, damos unos segundos extra para que cargue bien el perfil
        safe_sleep(random.uniform(3, 5), task_id=task_id)
        texto_perfil = driver.execute_script("return document.body.innerText;")
        
        driver.quit()
        from services.linkedin_bot import worker_drivers
        worker_drivers.pop(user_id, None)
        
        update_task(task_id, progress=70, message="Analizando perfil con IA...")
        resultado_ia = redactar_mensaje_conexion(name, texto_perfil)
        
        update_task(task_id, status='done', progress=100, message="Análisis completado", result=json.dumps(resultado_ia))
        
    except InterruptedError as e: 
        update_task(task_id, status='error', error=str(e), message="Tarea detenida")
    except Exception as e:
        logger.error(f"Error crítico en analyze_profile: {e}")
        update_task(task_id, status='error', error=f"Error IA: {str(e)}", message="Error crítico.")