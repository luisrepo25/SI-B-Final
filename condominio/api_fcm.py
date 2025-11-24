from rest_framework import serializers, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import FCMDevice


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ('id', 'registration_id', 'tipo_dispositivo', 'nombre', 'activo')


class FCMDeviceViewSet(viewsets.ModelViewSet):
    queryset = FCMDevice.objects.all()
    serializer_class = FCMDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        perfil = getattr(self.request.user, 'perfil', None)
        if not perfil:
            return FCMDevice.objects.none()
        return FCMDevice.objects.filter(usuario=perfil)

    def perform_create(self, serializer):
        perfil = getattr(self.request.user, 'perfil', None)
        serializer.save(usuario=perfil)
    
    def get_permissions(self):
        """
        Permitir registro sin autenticación para que el frontend pueda
        registrar dispositivos antes del login.
        """
        if self.action == 'registrar':
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def registrar(self, request):
        """
        Registra un dispositivo FCM. Requiere usuario_id en el body.
        
        POST /api/fcm-dispositivos/registrar/
        Body: {
            "usuario_id": 123,
            "registration_id": "token_fcm...",
            "tipo_dispositivo": "web",
            "nombre": "Chrome en Windows"
        }
        """
        from condominio.models import Usuario
        
        # Obtener datos del request
        usuario_id = request.data.get('usuario_id')
        token = request.data.get('registration_id')
        tipo = request.data.get('tipo_dispositivo', 'web')
        nombre = request.data.get('nombre')
        
        if not token:
            return Response({'error': 'registration_id es requerido'}, status=400)
        
        # Si hay usuario autenticado, usarlo
        if request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
            if not perfil:
                return Response({'error': 'Usuario autenticado sin perfil'}, status=400)
        # Si no hay usuario autenticado pero se envió usuario_id, usarlo
        elif usuario_id:
            try:
                perfil = Usuario.objects.get(id=usuario_id)
            except Usuario.DoesNotExist:
                return Response({'error': f'Usuario {usuario_id} no encontrado'}, status=404)
        else:
            return Response({'error': 'Se requiere autenticación o usuario_id'}, status=400)
        
        # Crear o actualizar dispositivo
        obj, creado = FCMDevice.objects.update_or_create(
            registration_id=token,
            defaults={'usuario': perfil, 'tipo_dispositivo': tipo, 'nombre': nombre, 'activo': True}
        )
        
        return Response({
            'creado': creado,
            'dispositivo_id': obj.id,
            'usuario': perfil.nombre
        })
