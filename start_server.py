#!/usr/bin/env python
"""
Script de inicio que ejecuta Gunicorn y el scheduler de campañas en paralelo.
"""
import os
import sys
import subprocess
import threading
import time

def run_scheduler():
    """Ejecutar el scheduler de campañas en un thread"""
    # Dar tiempo para que Django termine de inicializarse
    time.sleep(3)
    
    try:
        # Configurar Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        
        import django
        django.setup()
        
        # Importar y ejecutar el scheduler
        from condominio.scheduler_campanas import ejecutar_campanas_job
        import schedule
        
        # Programar ejecución cada minuto
        schedule.every(1).minutes.do(ejecutar_campanas_job)
        
        print("🤖 [SCHEDULER] Iniciado. Verificando campañas cada 1 minuto...", flush=True)
        sys.stdout.flush()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(30)  # Verificar cada 30 segundos
            except Exception as e:
                print(f"❌ [SCHEDULER] Error: {e}", flush=True)
                sys.stdout.flush()
                time.sleep(60)
    except Exception as e:
        print(f"❌ [SCHEDULER] Error fatal al iniciar: {e}", flush=True)
        sys.stdout.flush()

if __name__ == '__main__':
    print("=" * 60, flush=True)
    print("🚀 [START_SERVER.PY] INICIANDO...", flush=True)
    print("=" * 60, flush=True)
    sys.stdout.flush()
    
    print("✅ Iniciando sistema...", flush=True)
    sys.stdout.flush()
    
    # Iniciar scheduler en un thread daemon
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    print(f"✅ Thread del scheduler iniciado", flush=True)
    print(f"🚀 Iniciando Gunicorn...", flush=True)
    sys.stdout.flush()
    
    # Ejecutar Gunicorn directamente (reemplaza el proceso)
    os.execvp('gunicorn', ['gunicorn', 'config.wsgi:application', '--bind', '0.0.0.0:8080'])
