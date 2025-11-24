import os
import time
import schedule
import threading
import platform
from datetime import datetime
from .backup_full import run_backup, cleanup_old_automatic_backups

# =====================================================
# 🌎 Zona horaria (America/La_Paz)
# =====================================================
os.environ['TZ'] = 'America/La_Paz'
if platform.system() != "Windows":  
    time.tzset()

# =====================================================
# ⏰ Programador de Backups Automáticos
# =====================================================

def run_automatic_backup():
    """
    Ejecuta un backup automático usando la función principal existente
    """
    print(f"🤖 [BACKUP AUTOMÁTICO] Iniciando backup automático...")
    try:
        run_backup(
            include_backend=True,
            include_db=True, 
            include_frontend=True,  
            db_type="postgres",
            automatic=True
        )
        print("✅ Backup automático completado correctamente")
    except Exception as e:
        print(f"❌ Error en backup automático: {e}")



def start_automatic_backups():
    """Inicia el programador de backups automáticos en un hilo separado"""
    
    # Evitar duplicados si esta función se llama más de una vez
    schedule.clear('backups')

    # 🕒 Backups automáticos programados - sábados 17:30 hora Bolivia
    schedule.every().sunday.at("22:00").tag('backups').do(run_automatic_backup)

    print("🤖 Programador de backups automáticos iniciado")
    print("🕒 Zona horaria activa:", time.tzname, "| Hora actual:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    for job in schedule.get_jobs('backups'):
        print("📅 Backup programado:", job, "| Próxima ejecución:", job.next_run.strftime("%Y-%m-%d %H:%M:%S"))

    # Iniciar scheduler en segundo plano
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    return scheduler_thread



