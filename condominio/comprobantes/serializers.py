from rest_framework import serializers
from .models import ComprobantePago


class ComprobantePagoSerializer(serializers.ModelSerializer):
    reserva_detalle = serializers.StringRelatedField(source="reserva", read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)

    class Meta:
        model = ComprobantePago
        fields = "__all__"
