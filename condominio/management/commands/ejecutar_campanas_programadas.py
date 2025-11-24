"""
Management command para ejecutar campañas de notificación programadas.

Este comando debe ejecutarse periódicamente (ej. cada 5 minutos) mediante:
- Cron job en Linux/Mac
- Task Scheduler en Windows
- Celery Beat si está disponible

Uso:
    python manage.py ejecutar_campanas_programadas
    
Ejemplo de crontab (ejecutar cada 5 minutos):
    */5 * * * * cd /ruta/proyecto && python manage.py ejecutar_campanas_programadas >> /var/log/campanas.log 2>&1
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from condominio.models import CampanaNotificacion
from condominio.tasks import ejecutar_campana_notificacion


class Command(BaseCommand):
    help = 'Ejecuta campañas de notificación que están programadas y ya llegaron a su fecha de envío'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Modo simulación: muestra qué campañas se ejecutarían sin enviarlas realmente',
        )
        parser.add_argument(
            '--force-id',
            type=int,
            help='Forzar ejecución de una campaña específica por su ID (ignora estado y fecha)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force_id = options.get('force_id')
        
        if force_id:
            # Modo forzado: ejecutar una campaña específica
            self._ejecutar_campana_forzada(force_id, dry_run)
        else:
            # Modo normal: buscar y ejecutar campañas programadas
            self._ejecutar_campanas_programadas(dry_run)

    def _ejecutar_campanas_programadas(self, dry_run):
        """Busca y ejecuta campañas programadas cuya fecha ya llegó."""
        ahora = timezone.now()
        
        self.stdout.write(self.style.NOTICE(f'\n=== Verificando campañas programadas ({ahora}) ===\n'))
        
        # Buscar campañas programadas que ya llegaron a su fecha
        campanas = CampanaNotificacion.objects.filter(
            estado='PROGRAMADA',
            fecha_programada__lte=ahora
        ).order_by('fecha_programada')
        
        total = campanas.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No hay campañas programadas pendientes de ejecutar.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Encontradas {total} campañas para ejecutar:\n'))
        
        ejecutadas_ok = 0
        ejecutadas_error = 0
        
        for campana in campanas:
            tiempo_atraso = (ahora - campana.fecha_programada).total_seconds() / 60  # minutos
            
            self.stdout.write(
                f'\n📢 Campaña #{campana.id}: {campana.nombre}'
            )
            self.stdout.write(
                f'   Programada: {campana.fecha_programada}'
            )
            self.stdout.write(
                f'   Atraso: {tiempo_atraso:.1f} minutos'
            )
            self.stdout.write(
                f'   Destinatarios: {campana.total_destinatarios}'
            )
            
            if dry_run:
                self.stdout.write(self.style.WARNING('   [DRY-RUN] No se ejecutará realmente\n'))
                continue
            
            # Ejecutar la campaña
            try:
                self.stdout.write('   Ejecutando...')
                resultado = ejecutar_campana_notificacion(campana.id)
                
                if resultado['success']:
                    ejecutadas_ok += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   ✓ Completada: {resultado["total_enviados"]} enviados, '
                            f'{resultado["total_errores"]} errores'
                        )
                    )
                else:
                    ejecutadas_error += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'   ✗ Error: {resultado.get("mensaje", "Error desconocido")}'
                        )
                    )
            except Exception as e:
                ejecutadas_error += 1
                self.stdout.write(
                    self.style.ERROR(f'   ✗ Excepción: {str(e)}')
                )
                # Log la excepción completa
                import logging
                logger = logging.getLogger(__name__)
                logger.exception(f'Error ejecutando campaña {campana.id}')
        
        # Resumen final
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Resumen ==='
                f'\n✓ Ejecutadas exitosamente: {ejecutadas_ok}'
                f'\n✗ Con errores: {ejecutadas_error}'
                f'\nTotal procesadas: {ejecutadas_ok + ejecutadas_error}\n'
            )
        )

    def _ejecutar_campana_forzada(self, campana_id, dry_run):
        """Ejecuta una campaña específica por su ID (modo forzado)."""
        try:
            campana = CampanaNotificacion.objects.get(id=campana_id)
        except CampanaNotificacion.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Error: Campaña con ID {campana_id} no encontrada')
            )
            return
        
        self.stdout.write(
            self.style.NOTICE(f'\n=== Ejecución FORZADA de campaña #{campana_id} ===\n')
        )
        self.stdout.write(f'Nombre: {campana.nombre}')
        self.stdout.write(f'Estado actual: {campana.get_estado_display()}')
        self.stdout.write(f'Fecha programada: {campana.fecha_programada}')
        self.stdout.write(f'Destinatarios: {campana.total_destinatarios}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n[DRY-RUN] No se ejecutará realmente')
            )
            return
        
        # Advertencia si no está en estado PROGRAMADA
        if campana.estado != 'PROGRAMADA':
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  ADVERTENCIA: La campaña está en estado {campana.get_estado_display()}, '
                    'no en PROGRAMADA. ¿Desea continuar? (s/n): '
                ),
                ending=''
            )
            respuesta = input()
            if respuesta.lower() not in ['s', 'si', 'y', 'yes']:
                self.stdout.write(self.style.ERROR('Ejecución cancelada por el usuario'))
                return
        
        # Ejecutar
        try:
            self.stdout.write('\nEjecutando campaña...')
            resultado = ejecutar_campana_notificacion(campana_id)
            
            if resultado['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Campaña ejecutada exitosamente:'
                        f'\n  - Enviados: {resultado["total_enviados"]}'
                        f'\n  - Errores: {resultado["total_errores"]}'
                        f'\n  - Destinatarios: {resultado["total_destinatarios"]}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n✗ Error ejecutando campaña: {resultado.get("mensaje", "Error desconocido")}'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Excepción: {str(e)}')
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f'Error ejecutando campaña forzada {campana_id}')
