import os
import dropbox
from dropbox.files import WriteMode
import time
import platform
from datetime import datetime, timezone
from pytz import timezone as pytz_timezone

# Aplicar zona horaria Bolivia
os.environ["TZ"] = "America/La_Paz"
if platform.system() != "Windows":
    time.tzset()

def get_bolivia_now():
    return datetime.now(pytz_timezone("America/La_Paz"))

# ==========================================================
# 🔐 Carga del token de acceso desde el entorno (.env)
# ==========================================================

def get_dropbox_client():
    """
    Inicializa y devuelve un cliente de Dropbox usando el token
    almacenado en el archivo .env (variable DROPBOX_ACCESS_TOKEN).
    """
    token = os.getenv("DROPBOX_ACCESS_TOKEN")
    if not token:
        raise ValueError("⚠️ No se encontró DROPBOX_ACCESS_TOKEN en el entorno (.env)")
    return dropbox.Dropbox(token)


# ==========================================================
# ☁️ Subir backups a Dropbox
# ==========================================================

def upload_to_dropbox(file_path):
    """
    Sube un archivo ZIP de backup a Dropbox dentro de la carpeta /backups.
    Sobrescribe si el archivo ya existe.
    """
    try:
        dbx = get_dropbox_client()
        dest_path = f"/backups/{os.path.basename(file_path)}"

        with open(file_path, "rb") as f:
            dbx.files_upload(
                f.read(),
                dest_path,
                mode=WriteMode.overwrite
            )

        print(f"✅ Backup subido correctamente a Dropbox en: {dest_path}")
        return dest_path

    except Exception as e:
        print(f"❌ Error al subir a Dropbox: {e}")
        raise



    

def list_backups_dropbox():
    """
    Devuelve una lista con los backups almacenados en Dropbox,
    mostrando la hora convertida correctamente a hora local de Bolivia.
    """
    try:
        dbx = get_dropbox_client()
        result = dbx.files_list_folder("/backups")

        backups = []
        bolivia_tz = pytz_timezone("America/La_Paz")
        
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                # CORRECCIÓN: Manejo explícito de timezone
                utc_time = entry.server_modified
                
                # Asegurar que sea UTC
                if utc_time.tzinfo is None:
                    utc_time = utc_time.replace(tzinfo=timezone.utc)
                else:
                    utc_time = utc_time.astimezone(timezone.utc)
                
                # Convertir a Bolivia
                bolivia_time = utc_time.astimezone(bolivia_tz)

                backups.append({
                    "name": entry.name,
                    "path": entry.path_display,
                    "size_kb": round(entry.size / 1024, 2),
                    "modified": bolivia_time.strftime("%Y-%m-%d %H:%M:%S")
                })

        print(f"📂 Se encontraron {len(backups)} backups en Dropbox.")
        return backups

    except Exception as e:
        print(f"❌ Error al listar backups: {e}")
        return []


# ==========================================================
# 📋 Listar backups almacenados en Dropbox
# ==========================================================
# def list_backups_dropbox():
#     """
#     Devuelve una lista con los backups almacenados en Dropbox,
#     mostrando la hora convertida correctamente a hora local de Bolivia.
#     """
#     try:
#         dbx = get_dropbox_client()
#         result = dbx.files_list_folder("/backups")

#         backups = []
#         bolivia_tz = pytz_timezone("America/La_Paz")
        
#         for entry in result.entries:
#             if isinstance(entry, dropbox.files.FileMetadata):
#                 # ⚠️ CORRECCIÓN: Dropbox devuelve UTC, convertir EXPLÍCITAMENTE
#                 utc_time = entry.server_modified
                
#                 # Asegurar que tenga timezone UTC
#                 if utc_time.tzinfo is None:
#                     utc_time = utc_time.replace(tzinfo=timezone.utc)
#                 else:
#                     # Si ya tiene timezone, convertir a UTC primero
#                     utc_time = utc_time.astimezone(timezone.utc)
                
#                 # Convertir UTC a hora Bolivia
#                 bolivia_time = utc_time.astimezone(bolivia_tz)

#                 backups.append({
#                     "name": entry.name,
#                     "path": entry.path_display,
#                     "size_kb": round(entry.size / 1024, 2),
#                     "modified": bolivia_time.strftime("%Y-%m-%d %H:%M:%S")
#                 })

#         print(f"📂 Se encontraron {len(backups)} backups en Dropbox.")
#         return backups

#     except dropbox.exceptions.ApiError as e:
#         print(f"⚠️ Error al listar archivos en Dropbox: {e}")
#         raise

#     except Exception as e:
#         print(f"❌ Error inesperado al listar backups: {e}")
#         raise

# ==========================================================
# ⬇️ Descargar backups desde Dropbox
# ==========================================================

def download_from_dropbox(filename, local_dir):
    """
    Descarga un archivo ZIP desde Dropbox (carpeta /backups)
    al directorio local especificado (por ejemplo BACKUP_DIR).
    """
    try:
        dbx = get_dropbox_client()
        local_path = os.path.join(local_dir, filename)
        dropbox_path = f"/backups/{filename}"

        os.makedirs(local_dir, exist_ok=True)

        with open(local_path, "wb") as f:
            metadata, res = dbx.files_download(path=dropbox_path)
            f.write(res.content)

        print(f"⬇️ Backup descargado de Dropbox en: {local_path}")
        return local_path

    except dropbox.exceptions.HttpError as e:
        print(f"❌ Error HTTP al descargar {filename}: {e}")
        raise

    except Exception as e:
        print(f"❌ Error inesperado al descargar desde Dropbox: {e}")
        raise

def get_dropbox_share_link(filename):
    """
    Genera o recupera un enlace compartido de Dropbox para el archivo especificado.
    Retorna una URL de descarga directa (dl=1).
    """
    try:
        dbx = get_dropbox_client()
        dropbox_path = f"/backups/{filename}"

        links = dbx.sharing_list_shared_links(path=dropbox_path).links
        if links:
            url = links[0].url
        else:
            link = dbx.sharing_create_shared_link_with_settings(dropbox_path)
            url = link.url

        url = url.replace("?dl=0", "?dl=1")
        print(f"🔗 Enlace directo generado: {url}")
        return url

    except Exception as e:
        print(f"⚠️ No se pudo generar enlace compartido: {e}")
        return None
    



    