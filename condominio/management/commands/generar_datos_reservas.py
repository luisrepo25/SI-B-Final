# reservas/management/commands/generar_datos_reservas.py
import random
from datetime import datetime, date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from condominio.models import Reserva, Pago, Usuario, Servicio, Paquete  # ajusta imports a tu proyecto


class Command(BaseCommand):
    help = "Genera datos ficticios de Reservas y Pagos para pruebas."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cantidad',
            type=int,
            default=8000,
            help='Cantidad de reservas ficticias a generar (por defecto 8000).',
        )
        parser.add_argument(
            '--desde',
            type=str,
            default='2024-01-01',
            help='Fecha inicial (YYYY-MM-DD) desde la cual se generarán las reservas.',
        )

    def handle(self, *args, **options):
        cantidad = options['cantidad']
        try:
            fecha_desde = datetime.strptime(options['desde'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError("Formato de fecha inválido. Usa YYYY-MM-DD, ej: 2024-01-01")

        hoy = date.today()

        clientes = list(Usuario.objects.all())
        servicios = list(Servicio.objects.all())
        paquetes = list(Paquete.objects.all())

        if not clientes:
            raise CommandError("No hay Usuarios en la BD. Crea al menos un cliente antes de generar reservas.")

        self.stdout.write(self.style.WARNING(f"Generando {cantidad} reservas desde {fecha_desde} hasta {hoy}..."))

        reservas_a_crear = []
        for _ in range(cantidad):
            cliente = random.choice(clientes)

            # Fecha aleatoria entre fecha_desde y hoy
            dias_rango = (hoy - fecha_desde).days
            delta_dias = random.randint(0, max(dias_rango, 1))
            fecha_reserva = fecha_desde + timedelta(days=delta_dias)

            # hora de inicio y fin
            hora_inicio_random = random.randint(8, 18)  # entre las 8:00 y 18:00
            minuto_inicio_random = random.choice([0, 15, 30, 45])
            fecha_inicio = datetime.combine(
                fecha_reserva,
                datetime.min.time()
            ) + timedelta(hours=hora_inicio_random, minutes=minuto_inicio_random)

            duracion_horas = random.choice([2, 3, 4, 5, 6])
            fecha_fin = fecha_inicio + timedelta(hours=duracion_horas)

            estado_reserva = random.choice([e[0] for e in Reserva.ESTADOS])
            total = random.choice([150, 200, 280, 350, 400, 500, 650, 800])

            reserva = Reserva(
                fecha=fecha_reserva,
                fecha_inicio=timezone.make_aware(fecha_inicio),
                fecha_fin=timezone.make_aware(fecha_fin),
                estado=estado_reserva,
                total=total,
                moneda='BOB',
                cliente=cliente,
                servicio=random.choice(servicios) if servicios and random.random() < 0.7 else None,
                paquete=random.choice(paquetes) if paquetes and random.random() < 0.3 else None,
                # Campos de reprogramación, en la mayoría los dejamos vacíos
                fecha_original=None,
                fecha_reprogramacion=None,
                numero_reprogramaciones=0,
                motivo_reprogramacion=None,
                reprogramado_por=None,
            )
            reservas_a_crear.append(reserva)

        # Crear reservas en bulk
        reservas_creadas = Reserva.objects.bulk_create(reservas_a_crear, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Se crearon {len(reservas_creadas)} reservas."))

        # Ahora generamos pagos para la mayoría de reservas
        self.stdout.write(self.style.WARNING("Generando pagos ficticios..."))
        pagos_a_crear = []
        for reserva in reservas_creadas:
            # Por ejemplo, 80% de las reservas tienen un pago
            if random.random() < 0.8:
                fecha_pago = reserva.fecha  # mismo día que la reserva
                estado_pago = random.choice([e[0] for e in Pago.ESTADOS])
                metodo_pago = random.choice([m[0] for m in Pago.METODOS])

                pago = Pago(
                    monto=reserva.total,
                    metodo=metodo_pago,
                    fecha_pago=fecha_pago,
                    estado=estado_pago,
                    url_stripe="",  # opcional: podrías generar un string dummy
                    reserva=reserva,
                )
                pagos_a_crear.append(pago)

        pagos_creados = Pago.objects.bulk_create(pagos_a_crear, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Se crearon {len(pagos_creados)} pagos."))
        self.stdout.write(self.style.SUCCESS("✅ Datos ficticios generados correctamente."))
