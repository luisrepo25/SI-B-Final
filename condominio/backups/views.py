import os
import shutil
from django.conf import settings
from django.http import JsonResponse, FileResponse, Http404
from rest_framework.decorators import api_view
from datetime import datetime
import zipfile
from pathlib import Path
import traceback
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
# Importaciones de módulos internos
from .utils import BACKUP_DIR
from .restore_backup import restore_backup
from .upload_dropbox import (
    upload_to_dropbox,
    list_backups_dropbox,
    download_from_dropbox,
    get_dropbox_share_link
)



# ============================================================
# 🚀 CREAR BACKUP COMPLETO (POSTGRES + BACKEND + FIXTURES)
# ============================================================

@api_view(['POST'])
def crear_backup(request):
    """
    Crea un backup completo del sistema:
    - Incluye la base de datos PostgreSQL (usando DATABASE_URL)
    - Incluye el código backend (condominio, core, authz, config)
    - Incluye fixtures JSON
    - Sube el ZIP resultante a Dropbox y devuelve el enlace directo.
    """
    try:
        print("🚀 Iniciando creación de backup completo desde API...")

        from .backup_full import run_backup

        # Parámetros opcionales
        include_backend = request.data.get('include_backend', True)
        include_db = request.data.get('include_db', True)
        db_type = request.data.get('db_type', 'postgres')
        automatic = request.data.get('automatic', False)  # Nuevo parámetro

        # Ejecutar el proceso completo de backup
        run_backup(
            include_backend=include_backend,
            include_db=include_db,
            db_type=db_type,
            automatic=automatic  # Pasar el parámetro automático
        )

        # Buscar el archivo ZIP más reciente (COMPATIBILIDAD CON NUEVO SISTEMA)
        backup_patterns = [
            "manual_backup_*.zip",  # Nuevo sistema manual
            "auto_backup_*.zip",    # Nuevo sistema automático  
            "full_backup_*.zip"     # Sistema viejo (backwards compatibility)
        ]
        
        latest_backup = None
        latest_time = 0
        
        for pattern in backup_patterns:
            for backup_file in BACKUP_DIR.glob(pattern):
                file_time = backup_file.stat().st_mtime
                if file_time > latest_time:
                    latest_time = file_time
                    latest_backup = backup_file.name

        if not latest_backup:
            return JsonResponse({"error": "No se generó ningún archivo de backup."}, status=500)

        dropbox_path = f"/backups/{latest_backup}"

        # Intentar generar enlace de Dropbox
        link = get_dropbox_share_link(latest_backup)

        print(f"✅ Backup generado: {latest_backup}")
        print(f"🔗 Enlace Dropbox: {link}")

        return JsonResponse({
            "message": "Backup completo generado y subido correctamente.",
            "backup_file": latest_backup,
            "dropbox_path": dropbox_path,
            "dropbox_link": link or "No disponible",
            "backup_type": "manual" if "manual_backup" in latest_backup else "automatic"
        })

    except Exception as e:
        print("❌ Error al crear backup:", e)
        traceback.print_exc()
        return JsonResponse({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status=500)


# ============================================================
# 📋 LISTAR BACKUPS LOCALES (ACTUALIZADO)
# ============================================================

@api_view(['GET'])
def listar_backups(request):
    """Lista todos los backups locales, incluyendo manuales y automáticos"""
    backup_files = []
    
    # Incluir todos los tipos de backups
    patterns = ["manual_backup_*.zip", "auto_backup_*.zip", "full_backup_*.zip"]
    
    for pattern in patterns:
        for backup_file in BACKUP_DIR.glob(pattern):
            file_info = {
                'name': backup_file.name,
                'size_mb': round(backup_file.stat().st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(backup_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'manual' if 'manual_backup' in backup_file.name else 
                       'automatic' if 'auto_backup' in backup_file.name else 
                       'legacy'
            }
            backup_files.append(file_info)
    
    # Ordenar por fecha de modificación (más reciente primero)
    backup_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return JsonResponse({'backups': backup_files})


# ============================================================
# ♻️ RESTAURAR BACKUP LOCAL
# ============================================================

def parse_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return default


@api_view(['POST'])
def restaurar_backup(request):
    backup_file = request.data.get('backup_file')
    if not backup_file:
        return JsonResponse({'error': 'Debe especificar backup_file'}, status=400)

    backup_path = Path(BACKUP_DIR) / backup_file
    if not backup_path.exists():
        return JsonResponse({'error': 'Backup no encontrado'}, status=400)

    restore_code = parse_bool(request.data.get('restore_code', True))
    restore_db = parse_bool(request.data.get('restore_db', True))

    result = restore_backup(
        backup_zip_path=backup_path,
        restore_code=restore_code,
        restore_db=restore_db
    )

    if 'error' in result:
        return JsonResponse(result, status=400)
    return JsonResponse(result)


# ============================================================
# ⬇️ DESCARGAR BACKUP LOCAL
# ============================================================

@api_view(['GET'])
def descargar_backup(request, filename):
    """
    Descarga un archivo de backup por nombre.
    Ejemplo: /api/backups/download/manual_backup_20251030_154930.zip
    """
    file_path = Path(BACKUP_DIR) / filename
    if not file_path.exists() or not file_path.is_file():
        raise Http404("Backup no encontrado")

    response = FileResponse(open(file_path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{file_path.name}"'
    return response


# ============================================================
# 🗑️ ELIMINAR BACKUP LOCAL
# ============================================================

@api_view(['DELETE'])
def eliminar_backup(request, filename):
    """
    Elimina un archivo de backup por nombre.
    Ejemplo: /api/backups/delete/manual_backup_20251030_154930.zip
    """
    file_path = Path(BACKUP_DIR) / filename
    if not file_path.exists() or not file_path.is_file():
        return JsonResponse({'error': 'Backup no encontrado'}, status=404)

    try:
        os.remove(file_path)
        return JsonResponse({'message': f'Backup {filename} eliminado correctamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# ☁️ FUNCIONES DE DROPBOX
# ============================================================
@api_view(['GET'])
def listar_backups_dropbox(request):
    """Lista los backups almacenados en Dropbox (ordenados por fecha descendente)."""
    try:
        files = list_backups_dropbox()
        
        # ✅ ORDENAR por fecha DESCENDENTE (más reciente primero)
        files_ordenados = sorted(
            files, 
            key=lambda x: x.get('modified', ''), 
            reverse=True  # ← DESCENDENTE
        )
        
        print(f"🎯 Backups ordenados descendente: {len(files_ordenados)} archivos")
        if files_ordenados:
            print(f"🆕 Primer backup (más reciente): {files_ordenados[0]['name']}")
        
        return JsonResponse({'backups': files_ordenados})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['POST'])
def restaurar_desde_dropbox(request):
    """
    Restaura un backup alojado en Dropbox.
    Espera un JSON con:
    {
        "filename": "manual_backup_20251030_154930.zip",
        "type": "total" | "base" | "backend" | "frontend"
    }
    """
    filename = request.data.get('filename')
    restore_type = request.data.get('type', 'total').lower()

    if not filename:
        return JsonResponse({'error': 'Debe especificar el nombre del backup (filename)'}, status=400)

    try:
        # Descargar desde Dropbox al directorio local
        local_path = download_from_dropbox(filename, BACKUP_DIR)

        # Determinar qué restaurar
        restore_code = restore_type in ('total', 'backend', 'frontend')
        restore_db = restore_type in ('total', 'base')

        result = restore_backup(Path(local_path), restore_code=restore_code, restore_db=restore_db)

        return JsonResponse({
            'message': f"Backup '{filename}' restaurado como tipo '{restore_type}'",
            'result': result
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
####descargas 
@api_view(['GET'])
def descargar_desde_dropbox(request, filename):
    """
    GET /api/backups/dropbox/descargar/nombre_backup.zip
    """
    try:
        from .upload_dropbox import get_dropbox_share_link
        
        download_link = get_dropbox_share_link(filename)
        
        if not download_link:
            return JsonResponse({'error': f'Backup no encontrado: {filename}'}, status=404)
        
        # Redirigir directamente a Dropbox
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(download_link)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

###metodo de emergencia sin base
@api_view(['POST'])
@permission_classes([AllowAny])  # Sin autenticación normal
def restaurar_base_emergencia(request):
    """
    EMERGENCIA: Restaura solo la base de datos cuando se borró toda la base
    No requiere autenticación JWT (usa token de emergencia)
    """
    emergency_token = request.data.get('emergency_token')
    expected_token = os.environ.get('EMERGENCY_RESTORE_TOKEN')
    
    # Validar token de emergencia
    if not emergency_token or emergency_token != expected_token:
        return JsonResponse(
            {'error': 'Token de emergencia inválido'}, 
            status=403
        )
    
    filename = request.data.get('filename')
    if not filename:
        return JsonResponse(
            {'error': 'Debe especificar el nombre del backup'}, 
            status=400
        )
    
    try:
        # Descargar backup desde Dropbox
        from .upload_dropbox import download_from_dropbox
        local_path = download_from_dropbox(filename, BACKUP_DIR)
        
        # Restaurar SOLO la base de datos (sin tocar código)
        result = restore_backup(
            backup_zip_path=Path(local_path),
            restore_code=False,    # NO restaurar código
            restore_db=True        # SÍ restaurar base de datos
        )
        
        # Limpiar archivo temporal
        if Path(local_path).exists():
            os.remove(local_path)
        
        return JsonResponse({
            'message': f'✅ Base de datos restaurada exitosamente desde: {filename}',
            'backup_used': filename,
            'result': result
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Error en restauración de emergencia: {str(e)}'
        }, status=500)