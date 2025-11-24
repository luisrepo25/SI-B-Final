from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from .models import Usuario, Ticket, TicketMessage, Notificacion
from authz.models import Rol


class SupportFlowTests(TestCase):
    def setUp(self):
        # Obtener o crear roles (fixtures pueden ya contener roles)
        self.rol_soporte, _ = Rol.objects.get_or_create(nombre='Soporte')
        self.rol_cliente, _ = Rol.objects.get_or_create(nombre='Cliente')

        # Usuario cliente
        self.user_cli = User.objects.create_user(username='cliente', email='cli@example.com', password='cli123')
        self.cliente = Usuario.objects.create(user=self.user_cli, nombre='Cliente Uno', rol=self.rol_cliente)

        # Usuario agente
        self.user_age = User.objects.create_user(username='agente', email='age@example.com', password='age123')
        self.agente = Usuario.objects.create(user=self.user_age, nombre='Agente Uno', rol=self.rol_soporte)

        self.client = APIClient()

    def test_create_ticket_and_assign(self):
        # autenticar cliente
        self.client.force_authenticate(user=self.user_cli)
        # Usar perfil: la view espera request.user.perfil
        # Crear ticket
        resp = self.client.post('/api/tickets/', {'asunto': 'Problema X', 'descripcion': 'Detalle...'}, format='json')
        self.assertEqual(resp.status_code, 201)
        ticket_id = resp.data['id']
        ticket = Ticket.objects.get(pk=ticket_id)
        # Debe existir y creador correcto
        self.assertEqual(ticket.creador.nombre, 'Cliente Uno')
        # Si hay agente disponible, debe asignarse
        self.assertIn(ticket.estado, ['Abierto', 'Asignado'])

    def test_agent_responds_and_notification(self):
        # crear ticket por cliente
        ticket = Ticket.objects.create(creador=self.cliente, asunto='Asunto', descripcion='Desc')
        # autenticar agente
        self.client.force_authenticate(user=self.user_age)
        # crear mensaje
        resp = self.client.post('/api/ticket-messages/', {'ticket': ticket.id, 'texto': 'Respuesta del agente'}, format='json')
        self.assertEqual(resp.status_code, 201)
        # comprobar notificación al creador
        notis = Notificacion.objects.filter(usuario=self.cliente, tipo='ticket_respondido')
        self.assertTrue(notis.exists())

    def test_close_ticket(self):
        ticket = Ticket.objects.create(creador=self.cliente, asunto='Asunto', descripcion='Desc')
        self.client.force_authenticate(user=self.user_age)
        resp = self.client.post(f'/api/tickets/{ticket.id}/close/')
        self.assertEqual(resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, 'Cerrado')
