# condominio/backups/utils.py
import os
from pathlib import Path

try:
    from django.conf import settings
    BASE_DIR = Path(settings.BASE_DIR)
except Exception:
    # Fallback: calcula BASE_DIR manualmente si Django no está cargado
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

BACKUP_DIR = BASE_DIR / "condominio" / "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

