"""
Comando de Django para ejecutar el scheduler de campañas programadas.
Se ejecuta en background de forma continua.
"""
from django.core.management.base import BaseCommand
import schedule
import time
from condominio.scheduler_campanas import ejecutar_campanas_job


class Command(BaseCommand):
    help = 'Ejecuta el scheduler de campañas programadas en loop infinito'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("🤖 [SCHEDULER CMD] Iniciando scheduler de campañas"))
        self.stdout.write("=" * 60)
        
        # Programar ejecución cada minuto
        schedule.every(1).minutes.do(ejecutar_campanas_job)
        
        self.stdout.write(self.style.SUCCESS("✅ Job programado: cada 1 minuto"))
        self.stdout.write(self.style.SUCCESS("🔄 Iniciando loop infinito..."))
        
        # Loop infinito
        while True:
            try:
                schedule.run_pending()
                time.sleep(30)  # Verificar cada 30 segundos
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n⚠️ Scheduler detenido por usuario"))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error en scheduler: {e}"))
                time.sleep(60)  # Esperar 1 minuto antes de reintentar
