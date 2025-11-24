from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import ComprobantePago
from .serializers import ComprobantePagoSerializer


class ComprobantePagoViewSet(viewsets.ModelViewSet):
    """
    CRUD de comprobantes de pago (CU10 - Cliente).
    Los clientes suben sus comprobantes, los administradores los verifican.
    """
    queryset = ComprobantePago.objects.select_related("reserva", "cliente").order_by("-created_at")
    serializer_class = ComprobantePagoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["numero_transaccion", "estado"]
    filterset_fields = ["estado", "metodo_pago", "cliente"]

    def get_queryset(self):
        """
        🔒 Los clientes solo pueden ver sus propios comprobantes.
        Los administradores pueden ver todos.
        """
        user = self.request.user
        qs = super().get_queryset()

        # Si el usuario tiene perfil de cliente, filtrar solo sus comprobantes
        if hasattr(user, "perfil") and getattr(user.perfil.rol, "nombre", "").lower() == "cliente":
            return qs.filter(cliente=user.perfil)

        return qs

    def perform_create(self, serializer):
        """
        Asigna automáticamente el cliente al crear un comprobante.
        """
        serializer.save(cliente=self.request.user.perfil)
