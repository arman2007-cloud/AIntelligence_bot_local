"""
==============================================================================
JOBS RADAR ENGINE (jobs_radar.py)
Motor Delegado a n8n + Puntuación Semántica Local
==============================================================================
"""

import os
from utils import call_n8n_safely
from dotenv import load_dotenv

load_dotenv()

# --- Algoritmo de Puntuación Semántica Local ---
def _calcular_score_relevancia(titulo_encontrado: str, cargo_buscado: str) -> int:
    t_enc = titulo_encontrado.lower()
    c_bus = cargo_buscado.lower()
    score = 60
    
    if c_bus == t_enc:
        score = 98
    elif c_bus in t_enc:
        score = 88
    else:
        palabras_buscadas = c_bus.split()
        coincidencias = sum(1 for p in palabras_buscadas if p in t_enc)
        if coincidencias == len(palabras_buscadas):
            score = 80
        elif coincidencias > 0:
            score = 70

    if "senior" in c_bus and "junior" in t_enc: score -= 30
    if "junior" in c_bus and "senior" in t_enc: score -= 30
    if "lead" in c_bus and "intern" in t_enc: score -= 40

    return max(0, min(score, 100))

def _normalizar_vacante(job_title, company, location, url, score=85) -> dict:
    meta_parts = []
    if company and company not in ("Confidencial", ""):
        meta_parts.append(f"🏢 {company}")
    if location:
        meta_parts.append(f"📍 {location}")
        
    return {
        "job_title": job_title or "Unknown Role",
        "company": company or "Confidencial",
        "location": location or "Not specified",
        "url": url or "",
        "source": "LinkedIn",
        "score": score,
        "name": job_title or "Unknown Role",
        "meta": " · ".join(meta_parts)
    }

class JobsRadar:
    def buscar(self, cargo: str, ubicacion: str, **kwargs) -> dict:
        print(f"\n🔍 JobsRadar: Delegando búsqueda a n8n para '{cargo}' en '{ubicacion}'...")
        
        webhook_url = os.getenv("N8N_WEBHOOK_URL")
        if not webhook_url:
            print("⚠️ Error: N8N_WEBHOOK_URL no encontrada en .env")
            return {"vacantes": [], "total": 0}
            
        try:
            payload = {
                "action": "search_jobs",
                "cargo": cargo,
                "ubicacion": ubicacion
            }
            
            # Usamos nuestra capa de resiliencia de utils.py
            res_json = call_n8n_safely(webhook_url, payload)
            resultados_brutos = res_json.get("resultados", [])
            
            unicas = []
            vistos = set()
            
            for item in resultados_brutos:
                link = item.get("url", "")
                job = item.get("job_title", "Unknown")
                comp = item.get("company", "Confidencial")
                
                if link and link not in vistos and "linkedin.com/jobs" in link:
                    vistos.add(link)
                    score_calculado = _calcular_score_relevancia(job, cargo)
                    
                    unicas.append(_normalizar_vacante(
                        job_title=job, 
                        company=comp, 
                        location=ubicacion, 
                        url=link, 
                        score=score_calculado
                    ))
            
            unicas.sort(key=lambda x: x.get("score", 0), reverse=True)
            print(f"✅ JobsRadar completado: {len(unicas)} vacantes recibidas y puntuadas.")
            return {"vacantes": unicas[:15], "total": len(unicas[:15])}
            
        except Exception as e:
            print(f"⚠️ Error de conexión o procesamiento con n8n: {e}")
            return {"vacantes": [], "total": 0}