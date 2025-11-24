import os
import shutil
from datetime import datetime
from pathlib import Path
import subprocess
import zipfile
import dropbox
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DROPBOX_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
# Normalizar PROJECT_ROOT: si no está en env, usar la ruta relativa al propio archivo
try:
    PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT") or Path(__file__).resolve().parent.parent.parent)
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

BACKUP_ROOT = PROJECT_ROOT / "backups"
DB_FILE = PROJECT_ROOT / "db.sqlite3"  # Cambiar si usas PostgreSQL

# Crear carpeta de backup con timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = BACKUP_ROOT / f"backup_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)

print(f"Creando backup en: {backup_dir}")

# --- Backup base de datos ---
if DB_FILE.exists():
    shutil.copy(DB_FILE, backup_dir / DB_FILE.name)
    print(f"Base de datos copiada: {DB_FILE.name}")
else:
    print("No se encontró archivo de base de datos.")

# --- Backup de migraciones ---
migrations_dir = PROJECT_ROOT / "core" / "migrations"
if migrations_dir.exists():
    shutil.copytree(migrations_dir, backup_dir / "migrations")
    print("Migraciones copiadas.")

# --- Backup código backend ---
backend_backup_dir = backup_dir / "backend_code"
shutil.copytree(PROJECT_ROOT, backend_backup_dir, ignore=shutil.ignore_patterns('venv', '__pycache__', 'backups'))
print("Código backend copiado.")

# --- Dump de datos a JSON ---
json_backup_file = backup_dir / f"dump_{timestamp}.json"
subprocess.run(["python", "manage.py", "dumpdata", "--exclude", "auth.permission", "--exclude", "contenttypes", "--indent", "2", "--output", str(json_backup_file)])
print(f"Fixture JSON generada: {json_backup_file.name}")

# --- Comprimir todo ---
zip_file = BACKUP_ROOT / f"full_backup_{timestamp}.zip"
with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(backup_dir):
        for file in files:
            file_path = Path(root) / file
            zipf.write(file_path, file_path.relative_to(backup_dir))
print(f"Backup comprimido en: {zip_file}")

# --- Subir a Dropbox ---
dbx = dropbox.Dropbox(DROPBOX_TOKEN)
dropbox_path = f"/backups/full_backup_{timestamp}.zip"
with open(zip_file, "rb") as f:
    dbx.files_upload(f.read(), dropbox_path)
print(f"Backup subido a Dropbox: {dropbox_path}")

print("✅ Backup completo y subido a Dropbox.")
