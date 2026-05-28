"""
==============================================================================
DATA SOURCES ENGINE (data_sources.py)
Enrutador Inteligente (Smart Router) para Candidatos y Vacantes
==============================================================================
"""

from config import N8N_WEBHOOK_URL
from utils import call_n8n_safely
from jobs_radar import JobsRadar

class MultiSourceEngine:

    def __init__(self):
        # 1. Traemos la configuración de forma segura y centralizada
        self.n8n_webhook_url = N8N_WEBHOOK_URL
        if not self.n8n_webhook_url:
            print("⚠️ ADVERTENCIA: N8N_WEBHOOK_URL no definida en config.py/.env. La búsqueda de candidatos fallará.")

    # ==========================================================================
    # 1. MOTOR DE CANDIDATOS (n8n con Serper)
    # ==========================================================================
    def buscar_candidatos(self, cargo: str, ubicacion: str, pages: int = 1) -> list:
        print(f"🧠 SMART ROUTER: Delegando candidatos a n8n para '{cargo}' en '{ubicacion}' (Páginas: {pages})...")
        resultados_totales = []

        for pagina in range(1, pages + 1):
            print(f"   -> Extrayendo página {pagina} de candidatos...")
            try:
                # 2. USAMOS NUESTRO MOTOR DE REINTENTOS SEGURO
                datos_n8n = call_n8n_safely(
                    self.n8n_webhook_url,
                    params={"cargo": cargo, "ubicacion": ubicacion, "page": pagina}
                )
                
                if not datos_n8n:
                    continue

                for item in datos_n8n:
                    data = item.get("json", item) if isinstance(item, dict) else item
                    if "error" in data:
                        continue

                    data_lower = {k.lower().strip(): v for k, v in data.items()}
                    url_perfil = data_lower.get("profile url", data_lower.get("url", ""))
                    
                    if not url_perfil or "linkedin.com/in/" not in url_perfil:
                        continue

                    try: 
                        score = int(str(data_lower.get("score", 50)).replace("%", "").strip())
                    except ValueError: 
                        score = 50

                    resultados_totales.append({
                        "name":      data_lower.get("name", "Unknown"),
                        "job_title": data_lower.get("job title", cargo),
                        "company":   data_lower.get("current company", data_lower.get("company", "Not specified")),
                        "location":  ubicacion,
                        "url":       url_perfil,
                        "score":     score,
                        "source":    f"n8n Sourcing (Pág {pagina})",
                    })

            except Exception as e:
                print(f"❌ Error crítico en página {pagina} de candidatos: {e}")

        # Limpiamos duplicados por URL
        candidatos_unicos = {c['url']: c for c in resultados_totales}.values()
        print(f"✅ Búsqueda completada. Total candidatos únicos: {len(candidatos_unicos)}")
        
        return sorted(list(candidatos_unicos), key=lambda x: x.get("score", 0), reverse=True)


    # ==========================================================================
    # 2. MOTOR DE VACANTES (JobsRadar Local)
    # ==========================================================================
    def buscar_vacantes(self, cargo: str, ubicacion: str, pages: int = 1) -> list:
        """Usa el radar de Python directamente para evitar bloqueos de Google Cloud."""
        print(f"🚀 ACTIVANDO RADAR LOCAL para vacantes de '{cargo}' en '{ubicacion}'...")
        
        radar = JobsRadar()
        
        # 3. Delegamos totalmente la lógica al radar (que ya tiene su "Smart Loop")
        resumen_radar = radar.buscar(cargo, ubicacion)
        
        # El radar ya devuelve la lista limpia y perfecta con la estructura final
        vacantes_limpias = resumen_radar.get("vacantes", [])
        
        print(f"✅ JobsRadar Local devolvió {len(vacantes_limpias)} vacantes listas para la web.")
        return vacantes_limpias