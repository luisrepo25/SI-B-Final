"""
Scheduler para ejecutar campañas programadas automáticamente.

Este módulo inicia un scheduler que verifica cada minuto si hay campañas
que deben ser ejecutadas según su fecha/hora programada.
"""
import schedule
import time
import threading
from datetime import datetime
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

# Flag para evitar inicios múltiples
_scheduler_started = False
_scheduler_thread = None


def ejecutar_campanas_job():
    """
    Job que se ejecuta cada minuto para verificar y ejecutar campañas programadas.
    """
    try:
        logger.info(f"🔔 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando campañas programadas...")
        
        # Ejecutar el comando de Django que procesa campañas
        call_command('ejecutar_campanas_programadas', verbosity=0)
        
    except Exception as e:
        logger.error(f"❌ Error al ejecutar campañas programadas: {e}")


def run_scheduler():
    """
    Ejecuta el scheduler en un loop infinito.
    Esta función se ejecuta en un thread separado.
    """
    logger.info("🚀 Scheduler de campañas iniciado. Verificando cada 1 minuto...")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Verificar cada 30 segundos
        except Exception as e:
            logger.error(f"❌ Error en scheduler loop: {e}")
            time.sleep(60)  # Esperar 1 minuto antes de reintentar


def start_campaign_scheduler():
    """
    Inicia el scheduler de campañas programadas.
    Se ejecuta automáticamente al arrancar Django.
    """
    global _scheduler_started, _scheduler_thread
    
    # Evitar inicios múltiples
    if _scheduler_started:
        logger.warning("⚠️ Scheduler de campañas ya está corriendo")
        return
    
    _scheduler_started = True
    
    try:
        # Programar el job para que se ejecute cada minuto
        schedule.every(1).minutes.do(ejecutar_campanas_job)
        
        print("🤖 Programador de campañas iniciado")
        print(f"🕒 Intervalo: Cada 1 minuto")
        print(f"📅 Verificando campañas programadas automáticamente...")
        
        # Iniciar el scheduler en un thread separado
        _scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        _scheduler_thread.start()
        
        logger.info("✅ Scheduler de campañas configurado correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error al iniciar scheduler de campañas: {e}")
        _scheduler_started = False


def stop_campaign_scheduler():
    """
    Detiene el scheduler de campañas (útil para testing o shutdown).
    """
    global _scheduler_started
    
    schedule.clear()
    _scheduler_started = False
    
    logger.info("🛑 Scheduler de campañas detenido")
