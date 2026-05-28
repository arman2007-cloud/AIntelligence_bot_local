"""
==============================================================================
LOGGING CONFIGURATION (logging_config.py)
Sistema de logs rotativos y estructurados para producción
==============================================================================
"""

import os
import logging
import logging.handlers
import json
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """Logs en formato JSON — legibles por sistemas de monitorización."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("aintelligence_bot")
    logger.setLevel(logging.INFO)
    
    # Evitar handlers duplicados si Celery recarga el entorno
    if not logger.handlers:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
            datefmt="%H:%M:%S"
        ))
        
        file_handler = logging.handlers.RotatingFileHandler(
            "logs/bot_local.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(StructuredFormatter())
        
        logger.addHandler(console)
        logger.addHandler(file_handler)
        
    return logger