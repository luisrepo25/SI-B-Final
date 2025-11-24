import os
import shutil
from datetime import datetime
from pytz import timezone
import time
import platform
from pathlib import Path
import subprocess
import zipfile
import argparse
import sys
from dotenv import load_dotenv
from .upload_dropbox import upload_to_dropbox, get_dropbox_share_link

os.environ['TZ'] = 'America/La_Paz'
if platform.system() != "Windows":
    time.tzset()

def get_bolivia_now():
    return datetime.now(timezone("America/La_Paz"))
# =====================================================
# 🌍 Configuración inicial
# =====================================================

load_dotenv()  # Carga variables de entorno (.env)

# Rutas principales
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_ROOT = PROJECT_ROOT / "condominio" / "backups"
SQLITE_FILE = PROJECT_ROOT / "db.sqlite3"
MANAGE_PY = PROJECT_ROOT / "manage.py"

# =====================================================
# 🧩 Función principal de backup completo
# =====================================================

def run_backup(include_backend=True, include_db=True, include_frontend=True, db_type="postgres", automatic=False):
    from urllib.parse import urlparse

    # = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = get_bolivia_now().strftime("%Y%m%d_%H%M%S")

    # Diferenciar entre backup manual y automático
    if automatic:
        backup_type = "automático"
        temp_backup_dir = BACKUP_ROOT / f"auto_backup_temp_{timestamp}"
        #week_number = datetime.now().strftime("%Y-%U")  # Año-Semana
        week_number = get_bolivia_now().strftime("%Y-%U")  # Año-Semana
        zip_filename = f"auto_backup_{week_number}_{timestamp}.zip"
    else:
        backup_type = "manual"
        temp_backup_dir = BACKUP_ROOT / f"backup_temp_{timestamp}"
        zip_filename = f"manual_backup_{timestamp}.zip"
    
    os.makedirs(temp_backup_dir, exist_ok=True)

    print(f"📦 Creando backup {backup_type} en: {temp_backup_dir}")
    print("🕒 Hora local (Bolivia):", get_bolivia_now().strftime("%Y-%m-%d %H:%M:%S"))
    # =====================================================
    # 🗄️ Backup de base de datos (PostgreSQL o SQLite) - TU CÓDIGO ORIGINAL
    # =====================================================
    if include_db:
        # Intentar obtener la URL de conexión de distintas fuentes
        DATABASE_URL = (
            os.getenv("DATABASE_URL")
            or os.getenv("PG_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("RAILWAY_DATABASE_URL")
        )

        # 🔧 Reconstruir URL si contiene variables sin expandir (${...})
        def _mask_db_url(url: str) -> str:
            try:
                from urllib.parse import urlparse
                p = urlparse(url)
                pw_flag = "HAS_PASSWORD" if p.password else "NO_PASSWORD"
                return f"{p.scheme}://{p.username}:{pw_flag}@{p.hostname}:{p.port}{p.path}"
            except Exception:
                return "<invalid_db_url>"

        if not DATABASE_URL or "${" in DATABASE_URL:
            # Preferir variables POSTGRES_* si existen
            pg_user = os.getenv("PGUSER") or os.getenv("POSTGRES_USER") or "postgres"
            pg_password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or ""
            pg_host = os.getenv("RAILWAY_PRIVATE_DOMAIN") or os.getenv("RAILWAY_TCP_PROXY_DOMAIN") or "localhost"
            pg_port = os.getenv("PGPORT") or os.getenv("RAILWAY_TCP_PROXY_PORT") or "5432"
            pg_db = os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB") or "railway"

            DATABASE_URL = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
            print(f"⚙️ DATABASE_URL reconstruida automáticamente: {_mask_db_url(DATABASE_URL)}")

        # ------------------- PostgreSQL -------------------
        if db_type.lower() == "postgres":
            try:
                print("💾 Realizando backup de PostgreSQL completo...")

                parsed = urlparse(DATABASE_URL)
                pg_user = parsed.username
                pg_password = parsed.password
                pg_host = parsed.hostname
                pg_port = parsed.port or "5432"
                pg_db = parsed.path.lstrip("/")

                pg_dump_file = temp_backup_dir / f"postgres_dump_{timestamp}.sql"
                os.environ["PGPASSWORD"] = pg_password or ""

                # Comprobar si pg_dump existe en el PATH - ESTO FUNCIONA EN RAILWAY
                try:
                    from shutil import which
                    if not which("pg_dump"):
                        msg = "❌ pg_dump no está disponible en el PATH. Asegúrate de que la herramienta 'pg_dump' esté instalada en el entorno de ejecución."
                        print(msg)
                        # crear un archivo marker para facilitar diagnóstico remoto
                        marker = temp_backup_dir / "pg_dump_not_found.txt"
                        marker.write_text(msg)
                    else:
                        # Ejecutar pg_dump y capturar stdout/stderr para diagnóstico
                        result = subprocess.run([
                            "pg_dump",
                            "-U", pg_user,
                            "-h", pg_host,
                            "-p", str(pg_port),
                            "-d", pg_db,
                            "-F", "p",  # formato plano SQL (restaurable con psql)
                            "-f", str(pg_dump_file)
                        ], capture_output=True, text=True)

                        print(f"pg_dump returncode={result.returncode}")
                        if result.stdout:
                            print("pg_dump stdout:")
                            print(result.stdout)
                        if result.stderr:
                            print("pg_dump stderr:")
                            print(result.stderr)

                        if result.returncode == 0 and pg_dump_file.exists():
                            print(f"✅ Dump de PostgreSQL generado: {pg_dump_file.name}")
                        else:
                            msg = (
                                "❌ Error: No se generó dump de PostgreSQL. "
                                "Revisar credenciales, disponibilidad de pg_dump o permisos. "
                                f"Comando pg_dump intentó escribir en: {pg_dump_file}\n"
                            )
                            print(msg)
                            # escribir detalle de error para inspección remota
                            marker = temp_backup_dir / "pg_dump_failed.txt"
                            details = f"returncode={getattr(result, 'returncode', 'N/A')}\n"
                            details += f"stderr:\n{getattr(result, 'stderr', '')}\n"
                            details += f"stdout:\n{getattr(result, 'stdout', '')}\n"
                            marker.write_text(details)
                except Exception as e:
                    print(f"❌ Error ejecutando pg_dump: {e}")
            except Exception as e:
                print(f"❌ Error ejecutando pg_dump: {e}")
        else:
            # ------------------- SQLite -------------------
            if SQLITE_FILE.exists():
                shutil.copy(SQLITE_FILE, temp_backup_dir / SQLITE_FILE.name)
                print(f"🗄️ Base de datos SQLite copiada: {SQLITE_FILE.name}")
            else:
                print("⚠️ No se encontró archivo de base de datos SQLite.")

    # =====================================================
    # ⚙️ Backup del backend (código fuente) - TU CÓDIGO ORIGINAL
    # =====================================================
    if include_backend:
        include_dirs = ["condominio", "core", "authz", "config", "scripts"]
        exclude_patterns = ['venv', '__pycache__', 'backups', 'node_modules']

        backend_backup_dir = temp_backup_dir / "backend_code"
        os.makedirs(backend_backup_dir, exist_ok=True)

        print("🧠 Copiando código backend completo...")
        for include_dir in include_dirs:
            src = PROJECT_ROOT / include_dir
            if not src.exists():
                continue
            dst = backend_backup_dir / include_dir
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*exclude_patterns))
        print("✅ Código backend copiado correctamente.")

    # =====================================================
    # 🧾 Backup de datos JSON (fixtures) - TU CÓDIGO ORIGINAL
    # =====================================================
    if include_db:
        if MANAGE_PY.exists():
            # Diferenciar nombre para automáticos
            if automatic:
                json_backup_file = temp_backup_dir / f"auto_dump_{timestamp}.json"
            else:
                json_backup_file = temp_backup_dir / f"dump_{timestamp}.json"
                
            subprocess.run([
                sys.executable, str(MANAGE_PY), "dumpdata",
                "--exclude", "auth.permission",
                "--exclude", "contenttypes",
                "--indent", "2",
                "--output", str(json_backup_file)
            ])
            print(f"🧾 Fixture JSON generada: {json_backup_file.name}")
        else:
            print("⚠️ No se encontró manage.py, no se pudo generar fixture JSON.")

    # =====================================================
    # 🗜️ Comprimir todo el backup
    # =====================================================
    zip_file = BACKUP_ROOT / zip_filename
    print(f"📁 Comprimiendo backup {backup_type} en: {zip_file}")
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_backup_dir):
            for file in files:
                file_path = Path(root) / file
                zipf.write(file_path, file_path.relative_to(temp_backup_dir))
    print(f"✅ Backup {backup_type} comprimido en: {zip_file}")

    # =====================================================
    # ☁️ Subida a Dropbox + enlace directo - TU CÓDIGO ORIGINAL
    # =====================================================
    try:
        dest_path = upload_to_dropbox(zip_file)
        print(f"📤 Backup subido correctamente a Dropbox: {dest_path}")

        link = get_dropbox_share_link(os.path.basename(zip_file))
        if link:
            print(f"🔗 Enlace de descarga directa: {link}")
        else:
            print("⚠️ No se pudo generar el enlace compartido de Dropbox.")
    except Exception as e:
        print(f"⚠️ Error al subir o generar enlace en Dropbox: {e}")

    # =====================================================
    # 🧹 Limpieza final
    # =====================================================
    try:
        shutil.rmtree(temp_backup_dir)
        print("🧹 Carpeta temporal eliminada. Backup finalizado con éxito.")
    except Exception as e:
        print(f"⚠️ No se pudo eliminar carpeta temporal: {e}")

    # =====================================================
    # 🧹 Limpieza de backups automáticos antiguos (NUEVO)
    # =====================================================
    if automatic:
        cleanup_old_automatic_backups()


# =====================================================
# 🔄 SISTEMA DE BACKUPS AUTOMÁTICOS (NUEVO)
# =====================================================

def cleanup_old_automatic_backups():
    """Mantiene solo los backups automáticos de las últimas 4 semanas"""
    try:
        backup_files = list(BACKUP_ROOT.glob("auto_backup_*.zip"))
        backup_files.sort(key=os.path.getmtime)
        
        # Mantener máximo 4 backups automáticos
        if len(backup_files) > 4:
            files_to_delete = backup_files[:-4]  # Eliminar los más antiguos
            for file in files_to_delete:
                file.unlink()
                print(f"🗑️ Backup automático antiguo eliminado: {file.name}")
    except Exception as e:
        print(f"⚠️ Error limpiando backups antiguos: {e}")


# =====================================================
# 🔧 Ejecución desde CLI
# =====================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup Django completo (PostgreSQL + código + fixtures)")
    parser.add_argument("--no-backend", action="store_true", help="No incluir código backend")
    parser.add_argument("--no-db", action="store_true", help="No incluir base de datos")
    parser.add_argument("--db-type", choices=["sqlite", "postgres"], default="postgres", help="Tipo de base de datos")
    parser.add_argument("--auto", action="store_true", help="Ejecutar como backup automático")
    args = parser.parse_args()

    run_backup(
        include_backend=not args.no_backend,
        include_db=not args.no_db,
        db_type=args.db_type,
        automatic=args.auto
    )