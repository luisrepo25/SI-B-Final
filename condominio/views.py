from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

from .models import Campania, CampaniaServicio
from .serializer import CampaniaSerializer, CampaniaServicioSerializer


# --- Campania ---
class CampaniaViewSet(viewsets.ModelViewSet):
    """
    CRUD de campañas de descuento.
    """
    queryset = Campania.objects.all().order_by('-created_at')
    serializer_class = CampaniaSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["descripcion"]
    filterset_fields = ["tipo_descuento"]

    @action(detail=True, methods=["get"])
    def servicios(self, request, pk=None):
        """
        Retorna todos los servicios asociados a una campaña.
        """
        campania = self.get_object()
        relaciones = CampaniaServicio.objects.filter(campania=campania).select_related("servicio")
        serializer = CampaniaServicioSerializer(relaciones, many=True)
        return Response(serializer.data)


# --- CampaniaServicio ---
class CampaniaServicioViewSet(viewsets.ModelViewSet):
    """
    CRUD para las relaciones entre campañas y servicios.
    """
    queryset = CampaniaServicio.objects.select_related("campania", "servicio").order_by('-created_at')
    serializer_class = CampaniaServicioSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["campania", "servicio"]

    def get_queryset(self):
        """
        Permite filtrar por campania_id o servicio_id desde la URL.
        """
        queryset = super().get_queryset()
        campania_id = self.request.query_params.get("campania_id")
        servicio_id = self.request.query_params.get("servicio_id")

        if campania_id:
            queryset = queryset.filter(campania_id=campania_id)
        if servicio_id:
            queryset = queryset.filter(servicio_id=servicio_id)

        return queryset
