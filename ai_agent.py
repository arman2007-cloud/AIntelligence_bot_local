"""
==============================================================================
AI AGENT (ai_agent.py)
Motor de razonamiento con Alta Disponibilidad (Serie 2.5+)
==============================================================================
"""

import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from logging_config import setup_logging

load_dotenv(override=True)
logger = setup_logging()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def llamar_ia_con_reintentos(prompt: str, max_intentos=3) -> str:
    """
    Intenta llamar a la API. Si da error 503 (saturación), espera y reintenta.
    EXCLUSIVO para modelos Gemini 2.5 o superiores.
    """
    if not GEMINI_API_KEY:
        raise ValueError("API Key de Gemini no configurada en el .env local.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Orden de preferencia: Serie 2.5 exclusivamente
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-2.5-pro']
    
    for intento in range(max_intentos):
        for modelo in modelos_a_probar:
            try:
                logger.info(f"Probando {modelo} (Intento {intento + 1}/{max_intentos})...")
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    )
                )
                return response.text 
                
            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"Fallo en {modelo}: {error_str}")
                
                # Si es un error de sobrecarga (503) o límite (429), probamos el siguiente modelo
                if any(err in error_str for err in ["503", "429", "exhausted", "unavailable"]):
                    continue 
                else:
                    # Si es un error de formato o de API Key inválida, abortamos
                    raise e
        
        # Si hemos probado todos los modelos y fallan por saturación, backoff exponencial
        tiempo_espera = (intento + 1) * 3 
        logger.warning(f"⚠️ Servidores de IA saturados. Esperando {tiempo_espera}s para reintentar...")
        time.sleep(tiempo_espera)

    raise Exception("Límite de reintentos superado. Imposible contactar con Gemini 2.5+.")

def redactar_mensaje_conexion(nombre_candidato: str, texto_perfil: str) -> dict:
    texto_truncado = texto_perfil[:4000]
    
    prompt = f"""
    You are a Senior Tech Recruiter & Consultant at 'AIntelligence Research Ltd' in Malta.
    COMPANY CONTEXT: We solve business challenges through intelligent process automation and share actionable tech research to help leaders stay ahead of the curve.
    
    Your task is to write 3 DIFFERENT OPTIONS for a LinkedIn connection request message for this candidate.
    
    🚨 CRITICAL RULES FOR EACH MESSAGE (SYSTEM WILL CRASH IF YOU FAIL) 🚨
    1. LENGTH LIMIT: Each message MUST be strictly UNDER 170 CHARACTERS (including spaces). Use a maximum of 25 words.
    2. HYPER-PERSONALIZATION: Mention a specific detail from their profile (their company or a specific tech skill).
    3. VALUE ALIGNMENT: Seamlessly blend their background with AIntelligence's mission.
    4. STRUCTURE: Hook -> Value -> Short CTA.
    5. NO PLACEHOLDERS. Use actual extracted data.
    
    Return the response ONLY as a valid JSON with this exact structure:
    {{
        "opciones": [
            {{"enfoque": "Experience Focus", "mensaje": "Hi [Name]..."}},
            {{"enfoque": "Tech Skills Focus", "mensaje": "..."}},
            {{"enfoque": "Direct Value", "mensaje": "..."}}
        ]
    }}

    Candidate Name: {nombre_candidato}
    Text extracted from their LinkedIn profile:
    {texto_truncado}
    """

    try:
        texto_crudo = llamar_ia_con_reintentos(prompt)
        
        # Saneamiento extremo del JSON
        texto_limpio = texto_crudo.strip()
        if texto_limpio.startswith("```json"):
            texto_limpio = texto_limpio[7:-3].strip()
        elif texto_limpio.startswith("```"):
            texto_limpio = texto_limpio[3:-3].strip()
            
        resultado = json.loads(texto_limpio)
        logger.info(f"✅ IA generó opciones con éxito para {nombre_candidato}.")
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Fallo total de IA para {nombre_candidato}. Usando Fallback. Detalle: {e}")
        nombre_pila = nombre_candidato.split()[0] if nombre_candidato else "there"
        return {
            "opciones": [
                {
                    "enfoque": "Default (Fallback)", 
                    "mensaje": f"Hello {nombre_pila}, I noticed your tech background. At AIntelligence Research, we help leaders automate processes. Let’s connect and follow our updates."
                }
            ]
        }