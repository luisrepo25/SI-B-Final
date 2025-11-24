from .models import Ticket, Usuario


def assign_agent_to_ticket(ticket):
    """
    Asigna automáticamente un agente con rol 'Soporte' al ticket usando la estrategia de menor carga.
    """
    agentes = Usuario.objects.filter(rol__nombre__iexact='Soporte')
    if not agentes.exists():
        return None

    # Seleccionar agente con menor número de tickets abiertos/asignados
    agente_seleccionado = None
    menor_carga = None
    for agente in agentes:
        carga = Ticket.objects.filter(agente=agente, estado__in=['Asignado', 'Respondido']).count()
        if menor_carga is None or carga < menor_carga:
            menor_carga = carga
            agente_seleccionado = agente

    if agente_seleccionado:
        ticket.agente = agente_seleccionado
        ticket.estado = 'Asignado'
        ticket.save()
    return agente_seleccionado
