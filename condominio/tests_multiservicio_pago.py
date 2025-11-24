from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from datetime import date, datetime

from condominio.models import Usuario, Rol, Categoria, Servicio, Paquete, Reserva


class MultiservicioStripeFlowTest(TestCase):
    def setUp(self):
        # Usuario y perfil cliente
        self.user = User.objects.create_user(username='cliente', email='cliente@example.com', password='pass1234')
        rol = Rol.objects.create(nombre='cliente')
        self.perfil = Usuario.objects.create(user=self.user, nombre='Cliente', rol=rol)

        # Cat y dos servicios
        cat = Categoria.objects.create(nombre='Aventura')
        self.serv1 = Servicio.objects.create(
            titulo='Tour A', descripcion='Desc A', duracion='1D', capacidad_max=10,
            punto_encuentro='Plaza', categoria=cat, precio_usd=10
        )
        self.serv2 = Servicio.objects.create(
            titulo='Tour B', descripcion='Desc B', duracion='1D', capacidad_max=10,
            punto_encuentro='Plaza', categoria=cat, precio_usd=20
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_multiservicio_crea_paquete_y_checkout(self):
        # 1) Crear reserva multiservicio (2 servicios) -> debe generar Paquete personalizado y asociarlo
        payload = {
            'fecha': date.today().isoformat(),
            'estado': 'PENDIENTE',
            'total': '100.00',
            'moneda': 'BOB',
            'cliente': self.perfil.id,
            'servicios': [
                {'servicio': self.serv1.id, 'fecha': date.today().isoformat()},
                {'servicio': self.serv2.id, 'fecha': date.today().isoformat()},
            ]
        }

        resp = self.client.post('/api/reservas-multiservicio/', payload, format='json')
        self.assertEqual(resp.status_code, 201, msg=resp.data)

        reserva_id = resp.data['id']
        # Debe existir la Reserva y tener un Paquete asociado
        reserva = Reserva.objects.get(id=reserva_id)
        self.assertIsNotNone(reserva.paquete, 'La reserva multiservicio no generó un Paquete personalizado')
        self.assertTrue(Paquete.objects.filter(id=reserva.paquete_id, es_personalizado=True).exists())

        # 2) Crear checkout por reserva con Stripe (mock)
        with patch('core.views.stripe.checkout.Session.create') as mock_create:
            fake_session = MagicMock()
            fake_session.url = 'https://checkout.stripe.com/test_session'
            fake_session.id = 'cs_test_123'
            mock_create.return_value = fake_session

            resp2 = self.client.post('/api/crear-checkout-reserva/', {'reserva_id': reserva_id}, format='json')
            self.assertEqual(resp2.status_code, 200, msg=resp2.data)
            self.assertIn('checkout_url', resp2.data)
            self.assertEqual(resp2.data['checkout_url'], fake_session.url)
            self.assertEqual(resp2.data['session_id'], fake_session.id)
