from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from condominio.models import Usuario, Paquete, Bitacora
from authz.models import Rol
from datetime import date, datetime


class ReservaBitacoraTestCase(TestCase):
    def setUp(self):
        # Crear user y perfil
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='pass1234')
        rol = Rol.objects.create(nombre='cliente')
        self.perfil = Usuario.objects.create(user=self.user, nombre='Tester', rol=rol)

        # Crear paquete
        self.paquete = Paquete.objects.create(
            nombre='Paquete Test',
            descripcion='Desc',
            duracion='1D',
            precio_base=100.00,
            precio_bob=700.00,
            cupos_disponibles=10,
            cupos_ocupados=0,
            fecha_inicio=date.today(),
            fecha_fin=date.today(),
            punto_salida='Plaza',
        )

        self.client = APIClient()
        # Autenticar con el usuario creado
        self.client.force_authenticate(user=self.user)

    def test_crear_reserva_genera_bitacora(self):
        payload = {
            'fecha': date.today().isoformat(),
            'fecha_inicio': datetime.now().isoformat(),
            'fecha_fin': datetime.now().isoformat(),
            'total': '100.00',
            'moneda': 'BOB',
            'cliente_id': self.perfil.id,
            'paquete_id': self.paquete.id,
        }

        resp = self.client.post('/api/reservas/', payload, format='json')
        self.assertIn(resp.status_code, (200, 201))

        # Verificar que exista una bitacora con accion Crear Reserva y que describa el paquete
        logs = Bitacora.objects.filter(accion__icontains='Crear Reserva').order_by('-created_at')
        self.assertTrue(logs.exists(), 'No se encontró entrada de Bitacora para Crear Reserva')
        latest = logs.first()
        self.assertIn(f'paquete_id={self.paquete.id}', latest.descripcion)