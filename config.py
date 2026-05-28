"""
==============================================================================
GLOBAL CONFIGURATION SYSTEM (config.py)
Configuración centralizada y lectura de variables de entorno (Worker Local)
==============================================================================
"""

import os
from dotenv import load_dotenv

# override=True asegura que siempre lea el .env actual y no caché de Windows
load_dotenv(override=True)

# ------------------------------------------------------------------------------
# 1. LÍMITES Y COMPORTAMIENTO
# ------------------------------------------------------------------------------
MAX_CONNECTIONS_PER_DAY = int(os.getenv("MAX_CONEXIONES", "15"))

# ------------------------------------------------------------------------------
# 2. INTEGRACIONES DEL TRABAJADOR
# ------------------------------------------------------------------------------
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

# ------------------------------------------------------------------------------
# 3. BROWSER ENGINE (Selenium Profiles)
# ------------------------------------------------------------------------------
BROWSER_PROFILE_DIR = os.path.expanduser("~/.aintelligence/profile")

# ------------------------------------------------------------------------------
# 4. MALTA INTELLIGENCE CONTEXT (Lead Scoring)
# ------------------------------------------------------------------------------
MALTA_SECTORS = [
    "iGaming", "Gaming", "Fintech", "Finance", "Blockchain",
    "Crypto", "Technology", "IT", "Software", "Recruitment",
    "HR", "Hospitality", "Legal", "Compliance", "AML",
    "KYC", "Payments", "Insurance", "Aviation", "Maritime",
    "Education", "Healthcare", "Construction", "Real Estate",
]

MALTA_LOCATIONS = [
    "Malta", "Valletta", "Sliema", "St Julian", "St. Julian's",
    "Saint Julian", "Paceville", "Gzira", "Birkirkara", "Mosta",
    "San Gwann", "Swieqi", "Attard", "Mdina", "Gozo", "Rabat",
    "Naxxar", "Qormi", "Marsaskala", "Mellieha", "Bugibba",
    "St Paul's Bay", "San Pawl il-Bahar", "Msida", "Pietà",
    "Ta' Xbiex", "Floriana", "Marsa", "Zejtun", "Zabbar",
]

SENIOR_KEYWORDS = [
    "head", "director", "manager", "lead", "senior", "vp",
    "vice president", "chief", "cto", "ceo", "coo", "cfo",
    "founder", "co-founder", "partner", "principal", "president",
]

JUNIOR_KEYWORDS = [
    "student", "intern", "trainee", "junior", "graduate",
    "fresher", "entry level", "assistant", "apprentice",
]