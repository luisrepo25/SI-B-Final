from rest_framework import viewsets, permissions, filters, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

def get_user_perfil(user):
    """Safely get perfil from user object"""
    if user and hasattr(user, 'perfil'):
        return getattr(user, 'perfil', None)
    return None

# Helper to log into Bitacora
def log_bitacora(request, accion, descripcion=None):
    """Create a Bitacora entry using request context (user perfil and IP).

    descripcion: optional free text describing the change; if callable, it will be called
    with the saved instance to produce a description.
    """
    try:
        Bitacora = __import__('condominio.models', fromlist=['Bitacora']).Bitacora
        # try to resolve perfil from request.user
        perfil = None
        user = getattr(request, 'user', None)
        perfil = get_user_perfil(user)

        # Determine IP
        ip = None
        # Common headers for real client IPs behind proxies
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            ip = xff.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        Bitacora.objects.create(usuario=perfil, accion=accion, descripcion=(descripcion or ''), ip_address=ip)
    except Exception:
        # Avoid failing the main operation if logging fails
        pass


# Audited base viewset: automatic Bitacora entries for CRUD
class AuditedModelViewSet(viewsets.ModelViewSet):
    """ModelViewSet that writes Bitacora entries on create/update/destroy.

    Subclasses may override or call super() for custom behavior.
    """
    def _make_description(self, action, instance):
        # Default description: ModelName id=.. repr
        try:
            model_name = instance.__class__.__name__
            pk = getattr(instance, 'id', None)
            return f"{model_name} {action} id={pk}"
        except Exception:
            return f"{action}"

    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            descripcion = self._make_description('creado', instance)
            log_bitacora(self.request, f'Crear {instance.__class__.__name__}', descripcion)
        except Exception:
            pass

    def perform_update(self, serializer):
        instance = self.get_object()
        fecha_anterior = instance.fecha_inicio
        data = self.request.data

        # Manejar reprogramado_por como int si viene como string
        reprogramado_por = data.get('reprogramado_por')
        if reprogramado_por is not None and isinstance(reprogramado_por, str) and reprogramado_por.isdigit():
            from condominio.models import Usuario
            reprogramado_por_obj = Usuario.objects.filter(id=int(reprogramado_por)).first()
            serializer.validated_data['reprogramado_por'] = reprogramado_por_obj

        updated_instance = serializer.save()
        try:
            descripcion = self._make_description('actualizado', updated_instance)
            log_bitacora(self.request, f'Actualizar {updated_instance.__class__.__name__}', descripcion)
        except Exception:
            pass

        # Lógica de reprogramación SIEMPRE que venga fecha_reprogramacion
        nueva_fecha = data.get('fecha_reprogramacion') or getattr(updated_instance, 'fecha_reprogramacion', None)
        motivo = data.get('motivo_reprogramacion') or getattr(updated_instance, 'motivo_reprogramacion', '')
        if nueva_fecha:
            # Si es la primera reprogramación, guardar fecha_original
            if not updated_instance.fecha_original:
                updated_instance.fecha_original = fecha_anterior
            updated_instance.fecha_reprogramacion = nueva_fecha
            updated_instance.numero_reprogramaciones = (updated_instance.numero_reprogramaciones or 0) + 1
            updated_instance.estado = 'REPROGRAMADA'
            updated_instance.motivo_reprogramacion = motivo
            updated_instance.save()
            from condominio.models import HistorialReprogramacion
            HistorialReprogramacion.objects.create(
                reserva=updated_instance,
                fecha_anterior=fecha_anterior,
                fecha_nueva=nueva_fecha,
                motivo=motivo,
                reprogramado_por=updated_instance.reprogramado_por
            )

    def perform_destroy(self, instance):
        try:
            descripcion = self._make_description('eliminado', instance)
            log_bitacora(self.request, f'Eliminar {instance.__class__.__name__}', descripcion)
        except Exception:
            pass
        instance.delete()
from .models import (
    Categoria, Proveedor, Servicio, Suscripcion, Usuario, Campania, Paquete, PaqueteServicio, Cupon, Reserva, Visitante,
    ReservaVisitante, CampaniaServicio, Pago, ReglaReprogramacion, 
    HistorialReprogramacion, ConfiguracionGlobalReprogramacion, Reprogramacion, Plan
)
from .serializer import (
    CategoriaSerializer, ServicioSerializer, UsuarioSerializer, CampaniaSerializer,
    CuponSerializer, ReservaSerializer, VisitanteSerializer, ReservaVisitanteSerializer,
    CampaniaServicioSerializer, PagoSerializer, ReglaReprogramacionSerializer,
    HistorialReprogramacionSerializer, ConfiguracionGlobalReprogramacionSerializer,
    ReprogramacionSerializer, PaqueteCompletoSerializer, PaqueteSerializer, PerfilUsuarioSerializer,
    SoporteResumenSerializer, SuscripcionSerializer, ProveedorSerializer,PlanSerializer
)
from .serializer import TicketSerializer, TicketDetailSerializer, TicketMessageSerializer, NotificacionSerializer
from .serializer import BitacoraSerializer
from .models import Ticket, TicketMessage, Notificacion
from .utils import assign_agent_to_ticket
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models


# =====================================================
# 🏷️ CATEGORIA
# =====================================================
class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# 🧍 USUARIO
# =====================================================
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        # Siempre devolver 200 para usuarios autenticados.
        # Si existe el perfil, devolverlo serializado; si no, devolver un fallback público mínimo.
        user = request.user
        perfil = get_user_perfil(user)

        if perfil:
            # Usar el serializador público consistente con login/register
            from authz.serializer import PublicUsuarioSerializer
            serializer = PublicUsuarioSerializer(perfil)
            return Response(serializer.data)

        # Perfil no existe: devolver información pública mínima del user
        fallback = {
            'id': None,
            'user': user.id,
            'nombre': None,
            'rubro': None,
            'num_viajes': 0,
            'rol': None,
        }
        return Response(fallback)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def test_auth(self, request):
        """
        Endpoint de prueba para validar autenticación.
        
        GET /api/usuarios/test_auth/
        
        Retorna información del usuario autenticado para debugging.
        """
        return Response({
            'authenticated': True,
            'user_id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'is_active': request.user.is_active,
            'has_perfil': hasattr(request.user, 'perfil'),
            'perfil_id': request.user.perfil.id if hasattr(request.user, 'perfil') else None,
        })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def con_fcm(self, request):
        """
        Lista usuarios que tienen tokens FCM activos registrados.
        
        GET /api/usuarios/con_fcm/
        
        Query params opcionales:
        - rol: Filtrar por rol (ej: ?rol=Cliente)
        - search: Buscar por nombre (ej: ?search=Luis)
        
        Retorna:
        - Lista de usuarios con al menos un dispositivo FCM activo
        - Incluye: id, nombre, email, rol, num_viajes, total_dispositivos_fcm
        
        NOTA: Temporalmente con AllowAny para debug - cambiar a IsAuthenticated después
        """
        from django.db.models import Count, Q
        
        # Usuarios con al menos un dispositivo FCM activo
        usuarios = Usuario.objects.filter(
            user__is_active=True,
            dispositivos_fcm__activo=True
        ).distinct().annotate(
            total_dispositivos_fcm=Count('dispositivos_fcm', filter=Q(dispositivos_fcm__activo=True))
        )
        
        # Filtros opcionales
        rol = request.query_params.get('rol')
        if rol:
            usuarios = usuarios.filter(rol__nombre=rol)
        
        search = request.query_params.get('search')
        if search:
            usuarios = usuarios.filter(nombre__icontains=search)
        
        # Ordenar por nombre
        usuarios = usuarios.order_by('nombre')
        
        # Serializar respuesta
        data = [
            {
                'id': u.id,
                'nombre': u.nombre,
                'email': u.user.email if hasattr(u, 'user') and u.user else None,
                'rol': u.rol.nombre if u.rol else None,
                'telefono': u.telefono,
                'num_viajes': u.num_viajes,
                'total_dispositivos_fcm': u.total_dispositivos_fcm,
            }
            for u in usuarios
        ]
        
        return Response({
            'count': len(data),
            'usuarios': data
        })


# =====================================================
# 👤 PERFIL DE USUARIO (Para clientes)
# =====================================================
class PerfilUsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para mostrar perfil completo del usuario con estadísticas
    Solo permite lectura - para editar usar el endpoint usuarios
    """
    serializer_class = PerfilUsuarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Solo devolver el perfil del usuario autenticado"""
        user = self.request.user
        perfil = get_user_perfil(user)
        if perfil:
            return Usuario.objects.filter(id=perfil.id)
        return Usuario.objects.none()
    
    @action(detail=False, methods=['get'])
    def mi_perfil(self, request):
        """Endpoint directo para obtener mi perfil completo"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PerfilUsuarioSerializer(perfil)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def mis_reservas(self, request):
        """Obtener todas las reservas del usuario autenticado"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        reservas = perfil.reservas.all().order_by('-created_at')
        
        # Serializar reservas básicas
        reservas_data = []
        for reserva in reservas:
            reservas_data.append({
                'id': reserva.id,
                'fecha': reserva.fecha,
                'estado': reserva.estado,
                'total': float(reserva.total),
                'moneda': reserva.moneda,
                'fecha_creacion': reserva.created_at,
                'cupon_usado': reserva.cupon.id if reserva.cupon else None
            })
        
        return Response({
            'count': len(reservas_data),
            'reservas': reservas_data
        })


# =====================================================
# 🎫 SOPORTE - PANEL API
# =====================================================
class SoportePanelViewSet(viewsets.ViewSet):
    """
    API específica para el panel de soporte de usuarios
    Proporciona información resumida y accesos directos
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """Resumen general del soporte para el usuario"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener resumen de soporte
        serializer = SoporteResumenSerializer(perfil)
        
        # Agregar información adicional del panel
        data = dict(serializer.data)
        data['panel_info'] = {
            'puede_crear_ticket': True,
            'limite_tickets_diarios': 5,  # Configurable
            'tickets_hoy': perfil.tickets_creados.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'tipos_soporte': [
                {'id': 'tecnico', 'nombre': 'Soporte Técnico'},
                {'id': 'reservas', 'nombre': 'Problemas con Reservas'},
                {'id': 'pagos', 'nombre': 'Consultas de Pagos'},
                {'id': 'general', 'nombre': 'Consulta General'}
            ]
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def mis_tickets(self, request):
        """Obtener todos los tickets del usuario"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        tickets = perfil.tickets_creados.all().order_by('-created_at')
        
        tickets_data = []
        for ticket in tickets:
            tickets_data.append({
                'id': ticket.id,
                'asunto': ticket.asunto,
                'descripcion': ticket.descripcion[:100] + '...' if len(ticket.descripcion) > 100 else ticket.descripcion,
                'estado': ticket.estado,
                'prioridad': ticket.prioridad,
                'fecha_creacion': ticket.created_at,
                'agente_asignado': ticket.agente.nombre if ticket.agente else None,
                'mensajes_count': ticket.messages.count()
            })
        
        return Response({
            'count': len(tickets_data),
            'tickets': tickets_data
        })
    
    @action(detail=False, methods=['post'])
    def crear_ticket_rapido(self, request):
        """Crear un ticket rápido desde el panel"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar límite diario
        tickets_hoy = perfil.tickets_creados.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        if tickets_hoy >= 5:  # Límite configurable
            return Response(
                {'error': 'Has alcanzado el límite diario de tickets (5)'}, 
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        asunto = request.data.get('asunto')
        descripcion = request.data.get('descripcion')
        tipo_soporte = request.data.get('tipo_soporte', 'general')
        
        if not asunto or not descripcion:
            return Response(
                {'error': 'Asunto y descripción son requeridos'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear ticket
        ticket = Ticket.objects.create(
            creador=perfil,
            asunto=f"[{tipo_soporte.upper()}] {asunto}",
            descripcion=descripcion,
            prioridad='Media'
        )
        
        # Asignar agente automáticamente
        assign_agent_to_ticket(ticket)
        
        return Response({
            'id': ticket.pk,
            'asunto': ticket.asunto,
            'estado': ticket.estado,
            'mensaje': 'Ticket creado exitosamente'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def notificaciones_soporte(self, request):
        """Obtener notificaciones relacionadas con soporte"""
        user = request.user
        perfil = get_user_perfil(user)
        
        if not perfil:
            return Response(
                {'error': 'No se encontró el perfil del usuario'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener notificaciones de los últimos 30 días
        desde = timezone.now() - timezone.timedelta(days=30)
        notificaciones = Notificacion.objects.filter(
            usuario=perfil,
            created_at__gte=desde
        ).order_by('-created_at')
        
        notif_data = []
        for notif in notificaciones:
            notif_data.append({
                'id': notif.pk,
                'tipo': notif.tipo,
                'leida': notif.leida,
                'fecha': notif.created_at,
                'datos': notif.datos
            })
        
        return Response({
            'count': len(notif_data),
            'notificaciones': notif_data
        })


# =====================================================
# 🎯 CAMPAÑA
# =====================================================
class CampaniaViewSet(viewsets.ModelViewSet):
    """
    CRUD de campañas de descuento.
    """
    queryset = Campania.objects.all().order_by('-created_at')
    serializer_class = CampaniaSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["descripcion"]
    filterset_fields = ["tipo_descuento"]

    @action(detail=True, methods=["get"])
    def servicios(self, request, pk=None):
        """
        Retorna los servicios asociados a esta campaña.
        """
        campania = self.get_object()
        relaciones = CampaniaServicio.objects.filter(campania=campania).select_related("servicio")
        serializer = CampaniaServicioSerializer(relaciones, many=True)
        return Response(serializer.data)


# =====================================================
# 📦 PAQUETES TURÍSTICOS (Nuevo modelo)
# =====================================================
class PaqueteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para paquetes turísticos completos con servicios/destinos incluidos
    Permite listar, ver detalle y filtrar paquetes disponibles
    """
    queryset = Paquete.objects.prefetch_related(
        'servicios__categoria', 
        'paqueteservicio_set__servicio__categoria',
        'campania'
    ).all()
    serializer_class = PaqueteSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Filtros personalizados para paquetes turísticos"""
        queryset = super().get_queryset()
        
        # Filtrar solo paquetes activos
        activo = self.request.query_params.get('activo', None)
        if activo and activo.lower() == 'true':
            queryset = queryset.filter(estado='Activo')
        
        # Filtrar solo paquetes disponibles (vigentes + con cupos)
        disponible = self.request.query_params.get('disponible', None)
        if disponible and disponible.lower() == 'true':
            from django.utils import timezone
            hoy = timezone.now().date()
            queryset = queryset.filter(
                estado='Activo',
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy,
                cupos_ocupados__lt=models.F('cupos_disponibles')
            )
        
        # Filtrar solo paquetes destacados
        destacado = self.request.query_params.get('destacado', None)
        if destacado and destacado.lower() == 'true':
            queryset = queryset.filter(destacado=True)
        
        # Filtrar por rango de precio
        precio_min = self.request.query_params.get('precio_min', None)
        precio_max = self.request.query_params.get('precio_max', None)
        if precio_min:
            queryset = queryset.filter(precio_base__gte=precio_min)
        if precio_max:
            queryset = queryset.filter(precio_base__lte=precio_max)
        
        # Filtrar por duración (contiene texto)
        duracion = self.request.query_params.get('duracion', None)
        if duracion:
            queryset = queryset.filter(duracion__icontains=duracion)
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='destacados')
    def destacados(self, request):
        """Endpoint para obtener solo paquetes destacados"""
        paquetes_destacados = self.get_queryset().filter(destacado=True)[:6]
        serializer = self.get_serializer(paquetes_destacados, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='disponibles')
    def disponibles(self, request):
        """Endpoint para obtener solo paquetes disponibles para reservar"""
        from django.utils import timezone
        hoy = timezone.now().date()
        
        paquetes_disponibles = self.get_queryset().filter(
            estado='Activo',
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
            cupos_ocupados__lt=models.F('cupos_disponibles')
        )
        
        serializer = self.get_serializer(paquetes_disponibles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='itinerario')
    def itinerario_detallado(self, request, pk=None):
        """Endpoint para obtener el itinerario completo de un paquete"""
        paquete = self.get_object()
        paquete_servicios = PaqueteServicio.objects.filter(
            paquete=paquete
        ).select_related('servicio__categoria').order_by('dia', 'orden')
        
        itinerario = {}
        for ps in paquete_servicios:
            dia_key = f"dia_{ps.dia}"
            if dia_key not in itinerario:
                itinerario[dia_key] = {
                    'dia': ps.dia,
                    'fecha_ejemplo': None,  # Se puede calcular con fechas reales
                    'actividades': []
                }
            
            itinerario[dia_key]['actividades'].append({
                'id': ps.id,
                'orden': ps.orden,
                'hora_inicio': ps.hora_inicio,
                'hora_fin': ps.hora_fin,
                'servicio_id': ps.servicio.pk,
                'titulo': ps.servicio.titulo,
                'descripcion': ps.servicio.descripcion,
                'categoria': ps.servicio.categoria.nombre if ps.servicio.categoria else None,
                'punto_encuentro': ps.punto_encuentro_override or ps.servicio.punto_encuentro,
                'notas': ps.notas,
                'servicios_incluidos': ps.servicio.servicios_incluidos
            })
        
        return Response({
            'paquete_id': paquete.pk,
            'paquete_nombre': paquete.nombre,
            'duracion_total': paquete.duracion,
            'itinerario': list(itinerario.values())
        })

    @action(detail=False, methods=['get'], url_path='mis_paquetes',
            permission_classes=[permissions.IsAuthenticated])
    def mis_paquetes(self, request):
        """Devuelve los paquetes asociados al usuario autenticado.

        Criterio: paquetes para los que el usuario tiene al menos una Reserva
        (Reserva.paquete != NULL) como cliente. No modifica ni interfiere con
        otros casos de uso (paquetes públicos, reservas individuales, etc.).
        """
        perfil = getattr(request.user, 'perfil', None)
        if not perfil:
            return Response([], status=200)

        qs = self.get_queryset().filter(
            reservas__cliente=perfil
        ).distinct().order_by('-created_at')

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# =====================================================
# 🎟️ CUPON
# =====================================================
class CuponViewSet(viewsets.ModelViewSet):
    queryset = Cupon.objects.select_related('campania').all()
    serializer_class = CuponSerializer
    permission_classes = [permissions.AllowAny]




# =====================================================
# 🏞️ SERVICIO
# =====================================================
class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.select_related('categoria').all()
    serializer_class = ServicioSerializer
    permission_classes = [permissions.AllowAny]




# =====================================================
# 🧾 RESERVA
# =====================================================
class ReservaViewSet(AuditedModelViewSet):
    queryset = (
        Reserva.objects
        .select_related('cliente', 'cupon', 'paquete', 'servicio')
        .all()
    )
    serializer_class = ReservaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['cliente__nombre', 'estado', 'moneda']
    filterset_fields = ['estado', 'moneda', 'cliente']

    # ===============================
    # CREACIÓN FORZANDO ESTADO PAGADA
    # ===============================
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['estado'] = 'PAGADA'
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        """Crear la reserva y registrar Bitacora incluyendo paquete_id/servicio_id si aplica."""
        instance = serializer.save()
        try:
            # Intentar obtener ids desde la instancia o desde el payload
            paquete_id = getattr(getattr(instance, 'paquete', None), 'id', None) or getattr(instance, 'paquete_id', None) or self.request.data.get('paquete_id')
            servicio_id = getattr(getattr(instance, 'servicio', None), 'id', None) or getattr(instance, 'servicio_id', None) or self.request.data.get('servicio_id')

            descripcion = f"Reserva creado id={getattr(instance, 'id', None)}"
            if paquete_id:
                descripcion += f" paquete_id={paquete_id}"
            if servicio_id:
                descripcion += f" servicio_id={servicio_id}"

            log_bitacora(self.request, 'Crear Reserva', descripcion)
        except Exception:
            # No bloquear creación por errores de bitácora
            pass

    # ===============================
    # FILTRAR SEGÚN USUARIO AUTENTICADO
    # ===============================
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        import logging
        logger = logging.getLogger("django")
        # Solo admins y soporte pueden ver todas las reservas
        if user.is_authenticated:
            perfil = get_user_perfil(user)
            logger.info(f"[ReservaViewSet.get_queryset] user={user} perfil={perfil} rol={(getattr(perfil, 'rol', None))} rol_nombre={(getattr(getattr(perfil, 'rol', None), 'nombre', None))}")
            admin_roles = ['admin', 'soporte', 'administrador']
            if perfil and hasattr(perfil, 'rol') and perfil.rol and perfil.rol.nombre.lower() in admin_roles:
                logger.info(f"[ReservaViewSet.get_queryset] ADMIN/SOPORTE: queryset count={queryset.count()} ids={[r.id for r in queryset]}")
                return queryset
            elif perfil:
                filtered = queryset.filter(cliente=perfil)
                logger.info(f"[ReservaViewSet.get_queryset] CLIENTE: queryset count={filtered.count()} ids={[r.id for r in filtered]}")
                return filtered
            else:
                logger.info(f"[ReservaViewSet.get_queryset] SIN PERFIL: queryset vacío")
                return queryset.none()
        # Si no está autenticado, no ve nada
        logger.info(f"[ReservaViewSet.get_queryset] NO AUTENTICADO: queryset vacío")
        return queryset.none()

    # ===============================
    # MIS RESERVAS (SOLO CLIENTE)
    # ===============================
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def mis_reservas(self, request):
        import logging
        logger = logging.getLogger("django")
        user = request.user
        perfil = get_user_perfil(user)

        logger.info(f"[mis_reservas] user={user} perfil={perfil} perfil_id={getattr(perfil, 'id', None)}")

        if not perfil:
            logger.info("[mis_reservas] No se encontró el perfil del usuario")
            return Response(
                {'error': 'No se encontró el perfil del usuario'},
                status=status.HTTP_404_NOT_FOUND
            )

        reservas = (
            Reserva.objects.filter(cliente=perfil)
            .select_related('cliente', 'cupon', 'paquete', 'servicio')
            .prefetch_related('visitantes__visitante')
            .order_by('-created_at')
        )

        logger.info(f"[mis_reservas] reservas count={reservas.count()} ids={[r.id for r in reservas]}")

        estado = request.query_params.get('estado')
        if estado:
            reservas = reservas.filter(estado__iexact=estado)
            logger.info(f"[mis_reservas] filtro estado={estado} count={reservas.count()}")

        fecha_desde = request.query_params.get('fecha_desde')
        if fecha_desde:
            reservas = reservas.filter(fecha__gte=fecha_desde)
            logger.info(f"[mis_reservas] filtro fecha_desde={fecha_desde} count={reservas.count()}")

        fecha_hasta = request.query_params.get('fecha_hasta')
        if fecha_hasta:
            reservas = reservas.filter(fecha__lte=fecha_hasta)
            logger.info(f"[mis_reservas] filtro fecha_hasta={fecha_hasta} count={reservas.count()}")

        serializer = ReservaSerializer(reservas, many=True)

        stats = {
            'total_reservas': reservas.count(),
            'por_estado': {
                nombre: reservas.filter(estado=clave).count()
                for clave, nombre in Reserva.ESTADOS
            },
            'activas': reservas.filter(estado__in=['PENDIENTE', 'CONFIRMADA', 'PAGADA', 'REPROGRAMADA']).count(),
            'completadas': reservas.filter(estado='COMPLETADA').count(),
            'canceladas': reservas.filter(estado='CANCELADA').count(),
        }

        data = {
            'estadisticas': stats,
            'reservas': serializer.data
        }

        logger.info(f"[mis_reservas] respuesta enviada reservas={len(serializer.data)}")

        return Response(data, status=status.HTTP_200_OK)
    # ===============================
    # RESERVAS ACTIVAS
    # ===============================
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def reservas_activas(self, request):
        user = request.user
        perfil = get_user_perfil(user)
        if not perfil:
            return Response({'error': 'No se encontró el perfil del usuario'}, status=status.HTTP_404_NOT_FOUND)

        reservas_activas = (
            Reserva.objects.filter(
                cliente=perfil,
                estado__in=['PENDIENTE', 'CONFIRMADA', 'PAGADA', 'REPROGRAMADA']
            )
            .select_related('cliente', 'cupon', 'paquete', 'servicio')
            .order_by('-created_at')
        )
        serializer = ReservaSerializer(reservas_activas, many=True)
        return Response({'count': reservas_activas.count(), 'reservas_activas': serializer.data})

    # ===============================
    # HISTORIAL COMPLETO
    # ===============================
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def historial_completo(self, request):
        user = request.user
        perfil = get_user_perfil(user)
        if not perfil:
            return Response({'error': 'No se encontró el perfil del usuario'}, status=status.HTTP_404_NOT_FOUND)

        reservas = (
            Reserva.objects.filter(cliente=perfil)
            .select_related('cliente', 'cupon', 'paquete', 'servicio', 'reprogramado_por')
            .prefetch_related('historial_reprogramaciones')
            .order_by('-created_at')
        )

        historial_data = []
        for reserva in reservas:
            reserva_data = dict(ReservaSerializer(reserva).data)
            historiales = HistorialReprogramacion.objects.filter(reserva=reserva)
            reserva_data['historial_reprogramaciones'] = [
                {
                    'fecha_anterior': h.fecha_anterior,
                    'fecha_nueva': h.fecha_nueva,
                    'motivo': h.motivo,
                    'reprogramado_por': h.reprogramado_por.nombre if h.reprogramado_por else None,
                    'fecha_cambio': h.created_at
                }
                for h in historiales
            ]
            historial_data.append(reserva_data)
        return Response({'count': len(historial_data), 'historial': historial_data})



# =====================================================
# 👥 VISITANTE
# =====================================================
class VisitanteViewSet(viewsets.ModelViewSet):
    queryset = Visitante.objects.all()
    serializer_class = VisitanteSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# 🔗 RESERVA_VISITANTE
# =====================================================
class ReservaVisitanteViewSet(viewsets.ModelViewSet):
    queryset = ReservaVisitante.objects.select_related('reserva', 'visitante').all()
    serializer_class = ReservaVisitanteSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            reserva = getattr(instance, 'reserva', None)
            visitante = getattr(instance, 'visitante', None)
            descripcion = f"Asociar Visitante id={getattr(visitante,'id',None)} nombre={getattr(visitante,'nombre',None)} {getattr(visitante,'apellido',None)} a Reserva id={getattr(reserva,'id',None)}"
            log_bitacora(self.request, 'Asociar Visitante a Reserva', descripcion)
        except Exception:
            pass


# =====================================================
# 🔗 CAMPAÑA_SERVICIO
# =====================================================
class CampaniaServicioViewSet(viewsets.ModelViewSet):
    """
    CRUD para las relaciones entre campañas y servicios.
    """
    queryset = CampaniaServicio.objects.select_related("campania", "servicio").order_by('-created_at')
    serializer_class = CampaniaServicioSerializer
    permission_classes = [permissions.AllowAny]
   
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["campania", "servicio"]

    def get_queryset(self):
        """
        Permite filtrar por campania_id o servicio_id.
        """
        queryset = super().get_queryset()
        campania_id = self.request.query_params.get("campania_id")
        servicio_id = self.request.query_params.get("servicio_id")

        if campania_id:
            queryset = queryset.filter(campania_id=campania_id)
        if servicio_id:
            queryset = queryset.filter(servicio_id=servicio_id)

        return queryset


# =====================================================
# 💳 PAGO
# =====================================================
class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.select_related('reserva').all()
    serializer_class = PagoSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# 🔁 REGLA_REPROGRAMACION
# =====================================================
class ReglaReprogramacionViewSet(viewsets.ModelViewSet):
    queryset = ReglaReprogramacion.objects.all()
    serializer_class = ReglaReprogramacionSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# 🔄 REPROGRAMACION
# =====================================================
class ReprogramacionViewSet(viewsets.ModelViewSet):
    queryset = Reprogramacion.objects.select_related('reserva').all()
    serializer_class = ReprogramacionSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# 📋 HISTORIAL_REPROGRAMACION
# =====================================================
class HistorialReprogramacionViewSet(viewsets.ModelViewSet):
    queryset = HistorialReprogramacion.objects.select_related('reserva', 'reprogramado_por').all()
    serializer_class = HistorialReprogramacionSerializer
    permission_classes = [permissions.AllowAny]


# =====================================================
# ⚙️ CONFIGURACION_GLOBAL_REPROGRAMACION
# =====================================================
class ConfiguracionGlobalReprogramacionViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionGlobalReprogramacion.objects.all()
    serializer_class = ConfiguracionGlobalReprogramacionSerializer
    permission_classes = [permissions.AllowAny]


# ==========================
# Soporte (Tickets)
# ==========================
class TicketViewSet(AuditedModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TicketDetailSerializer
        return TicketSerializer

    def perform_create(self, serializer):
        user = self.request.user
        try:
            perfil = getattr(user, "perfil", None)
        except Exception:
            perfil = None

        ticket = serializer.save(creador=perfil)
        assign_agent_to_ticket(ticket)

    def get_queryset(self):
        user = self.request.user
        try:
            perfil = getattr(user, "perfil", None)
        except Exception:
            return Ticket.objects.none()

        if perfil and hasattr(perfil, 'rol') and perfil.rol and perfil.rol.nombre.lower() == 'soporte':
            return Ticket.objects.all()
        return Ticket.objects.filter(creador=perfil)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        ticket = self.get_object()
        ticket.estado = 'Cerrado'
        ticket.save()
        Notificacion.objects.create(usuario=ticket.creador, tipo='ticket_cerrado', datos={'ticket_id': ticket.id})
        return Response({'status': 'cerrado'})


class TicketMessageViewSet(viewsets.ModelViewSet):
    queryset = TicketMessage.objects.all()
    serializer_class = TicketMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        try:
            perfil = getattr(user, "perfil", None)
        except Exception:
            perfil = None

        message = serializer.save(autor=perfil)
        ticket = message.ticket
        if perfil and perfil.rol and perfil.rol.nombre.lower() == 'soporte':
            ticket.estado = 'Respondido'
            ticket.save()
            Notificacion.objects.create(usuario=ticket.creador, tipo='ticket_respondido', datos={'ticket_id': ticket.id, 'message_id': message.id})


class NotificacionViewSet(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all()
    serializer_class = NotificacionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        try:
            perfil = getattr(user, "perfil", None)
        except Exception:
            return Notificacion.objects.none()
        return Notificacion.objects.filter(usuario=perfil)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        noti = self.get_object()
        noti.leida = True
        noti.save()
        return Response({'status': 'leida'})


class BitacoraViewSet(viewsets.ModelViewSet):
    queryset = __import__('condominio.models', fromlist=['Bitacora']).Bitacora.objects.all()
    serializer_class = BitacoraSerializer
    permission_classes = [permissions.IsAuthenticated]


# ============================================
# 📱 DISPOSITIVOS FCM
# ============================================
from .models import FCMDevice, CampanaNotificacion
from .serializer import FCMDeviceSerializer, CampanaNotificacionSerializer

class FCMDeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de dispositivos FCM.
    Permite registro y actualización de tokens desde la app móvil.
    """
    queryset = FCMDevice.objects.all()
    serializer_class = FCMDeviceSerializer
    
    def get_permissions(self):
        """
        - Registrar dispositivo: Permite sin autenticación (AllowAny)
        - Otras acciones: Requiere autenticación
        """
        if self.action == 'registrar':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """Usuarios normales solo ven sus propios dispositivos."""
        user = self.request.user
        if user.is_staff or (hasattr(user, 'perfil') and user.perfil.rol and user.perfil.rol.nombre.lower() in ['admin', 'administrador', 'soporte']):
            return FCMDevice.objects.all()
        
        if hasattr(user, 'perfil') and user.perfil:
            return FCMDevice.objects.filter(usuario=user.perfil)
        
        return FCMDevice.objects.none()
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def registrar(self, request):
        """
        Registra o actualiza un dispositivo FCM.
        
        POST /api/fcm-dispositivos/registrar/
        Body:
        {
            "registration_id": "token_fcm_del_dispositivo",
            "tipo_dispositivo": "android",  # opcional
            "nombre": "Mi Celular"  # opcional
        }
        
        Retorna:
        - 201: Dispositivo creado
        - 200: Dispositivo actualizado
        """
        registration_id = request.data.get('registration_id')
        
        if not registration_id:
            return Response(
                {'error': 'registration_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener usuario autenticado (si existe)
        perfil = None
        if request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
        
        if not perfil:
            return Response(
                {'error': 'Usuario no autenticado o sin perfil'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Buscar o crear dispositivo
        dispositivo, created = FCMDevice.objects.update_or_create(
            registration_id=registration_id,
            defaults={
                'usuario': perfil,
                'tipo_dispositivo': request.data.get('tipo_dispositivo', 'android'),
                'nombre': request.data.get('nombre', ''),
                'activo': True
            }
        )
        
        serializer = FCMDeviceSerializer(dispositivo)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        
        return Response({
            'mensaje': 'Dispositivo registrado exitosamente' if created else 'Dispositivo actualizado',
            'dispositivo': serializer.data
        }, status=status_code)
    
    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        """
        Desactiva un dispositivo (dejar de recibir notificaciones).
        
        POST /api/fcm-dispositivos/{id}/desactivar/
        """
        dispositivo = self.get_object()
        dispositivo.activo = False
        dispositivo.save(update_fields=['activo'])
        
        return Response({
            'mensaje': 'Dispositivo desactivado',
            'dispositivo_id': dispositivo.id
        })
    
    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """
        Activa un dispositivo.
        
        POST /api/fcm-dispositivos/{id}/activar/
        """
        dispositivo = self.get_object()
        dispositivo.activo = True
        dispositivo.save(update_fields=['activo'])
        
        return Response({
            'mensaje': 'Dispositivo activado',
            'dispositivo_id': dispositivo.id
        })


# ============================================
# 📢 CAMPAÑAS DE NOTIFICACIONES
# ============================================
class CampanaNotificacionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión administrativa de campañas de notificaciones push.
    Solo administradores pueden crear, modificar o ejecutar campañas.
    """
    queryset = CampanaNotificacion.objects.all()
    serializer_class = CampanaNotificacionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'tipo_audiencia', 'tipo_notificacion']
    search_fields = ['nombre', 'titulo', 'descripcion']
    ordering_fields = ['created_at', 'fecha_programada', 'fecha_enviada']
    ordering = ['-created_at']
    
    def get_permissions(self):
        """Solo administradores pueden crear, modificar o ejecutar acciones sobre campañas."""
        if self.action in ['create', 'update', 'partial_update', 'destroy', 
                          'preview', 'enviar_test', 'activar', 'cancelar']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Vista previa de la campaña sin enviar.
        
        GET /api/campanas-notificacion/{id}/preview/
        """
        campana = self.get_object()
        
        usuarios = campana.obtener_usuarios_objetivo()
        total = usuarios.count()
        muestra = usuarios[:50]
        
        destinatarios_preview = [
            {
                'id': u.id,
                'nombre': u.nombre,
                'email': u.user.email if hasattr(u, 'user') and u.user else None,
                'rol': u.rol.nombre if u.rol else None,
            }
            for u in muestra
        ]
        
        return Response({
            'campana': {
                'id': campana.id,
                'nombre': campana.nombre,
                'estado': campana.estado,
            },
            'contenido': {
                'titulo': campana.titulo,
                'cuerpo': campana.cuerpo,
                'tipo_notificacion': campana.tipo_notificacion,
            },
            'segmentacion': {
                'tipo_audiencia': campana.tipo_audiencia,
                'total_destinatarios': total,
            },
            'destinatarios_preview': destinatarios_preview,
            # ↓ Agregar a nivel raíz para compatibilidad con frontend
            'total_destinatarios': total,
        })
    
    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """
        Activa la campaña para envío inmediato o programado.
        
        POST /api/campanas-notificacion/{id}/activar/
        """
        from .tasks import ejecutar_campana_notificacion
        
        campana = self.get_object()
        
        if not campana.puede_activarse():
            return Response(
                {'error': f'No se puede activar una campaña en estado {campana.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        total_destinatarios = campana.calcular_destinatarios()
        
        if total_destinatarios == 0:
            return Response(
                {'error': 'La campaña no tiene destinatarios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        perfil = getattr(request.user, 'perfil', None)
        ejecutor_id = perfil.id if perfil else None
        
        if campana.enviar_inmediatamente or not campana.fecha_programada:
            # Envío inmediato
            resultado = ejecutar_campana_notificacion(campana.id, ejecutor_id)
            
            if resultado['success']:
                return Response({
                    'mensaje': 'Campaña ejecutada inmediatamente',
                    'estado': 'COMPLETADA',
                    'resultado': resultado
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Error al ejecutar la campaña',
                    'resultado': resultado
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Programar
            campana.estado = 'PROGRAMADA'
            campana.save(update_fields=['estado'])
            
            return Response({
                'mensaje': 'Campaña programada exitosamente',
                'estado': 'PROGRAMADA',
                'fecha_programada': campana.fecha_programada,
                'total_destinatarios': total_destinatarios
            }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def enviar_test(self, request, pk=None):
        """
        Envía una notificación de prueba al usuario actual.
        
        POST /api/campanas-notificacion/{id}/enviar_test/
        """
        from condominio.utils import enviar_notificacion_fcm
        
        campana = self.get_object()
        
        # Obtener perfil del usuario actual
        perfil = getattr(request.user, 'perfil', None)
        if not perfil:
            return Response(
                {'error': 'Usuario no tiene perfil asociado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtener dispositivos FCM del usuario
        dispositivos = FCMDevice.objects.filter(
            usuario=perfil,
            activo=True
        )
        
        if not dispositivos.exists():
            return Response(
                {'error': 'No tienes dispositivos FCM registrados. Por favor, inicia sesión desde la app móvil.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Enviar notificación de prueba a cada dispositivo
        enviados = 0
        errores = []
        
        for dispositivo in dispositivos:
            try:
                resultado = enviar_notificacion_fcm(
                    titulo=f"[TEST] {campana.titulo}",
                    cuerpo=f"{campana.cuerpo}\n\n🧪 Esta es una notificación de prueba.",
                    usuario=perfil,
                    tipo_notificacion=campana.tipo_notificacion,
                    datos_adicionales={
                        'campana_id': campana.id,
                        'es_test': True,
                        'test_enviado_por': request.user.email
                    }
                )
                
                if resultado.get('success'):
                    enviados += 1
                else:
                    errores.append(resultado.get('error', 'Error desconocido'))
            
            except Exception as e:
                errores.append(str(e))
        
        if enviados > 0:
            return Response({
                'mensaje': f'Notificación de prueba enviada exitosamente',
                'dispositivos_alcanzados': enviados,
                'errores': errores if errores else None,
                'contenido_enviado': {
                    'titulo': f"[TEST] {campana.titulo}",
                    'cuerpo': campana.cuerpo,
                    'tipo': campana.tipo_notificacion
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'No se pudo enviar la notificación de prueba',
                'errores': errores
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """
        Cancela una campaña en estado BORRADOR o PROGRAMADA.
        
        POST /api/campanas-notificacion/{id}/cancelar/
        """
        campana = self.get_object()
        
        if not campana.puede_cancelarse():
            return Response(
                {'error': f'No se puede cancelar una campaña en estado {campana.get_estado_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campana.estado = 'CANCELADA'
        campana.save(update_fields=['estado'])
        
        return Response({
            'mensaje': 'Campaña cancelada exitosamente',
            'estado': 'CANCELADA'
        }, status=status.HTTP_200_OK)

from rest_framework.views import APIView
from .serializer import ReservaConServiciosSerializer, ReservaSalidaSerializer

class ReservaMultiServicioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ReservaConServiciosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reserva = serializer.save()
        # Re-serializar con un serializer de salida que no incluye el campo de entrada 'servicios'
        out = ReservaSalidaSerializer(reserva)
        return Response(out.data, status=status.HTTP_201_CREATED)


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.select_related('usuario').all()
    serializer_class = ProveedorSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['nombre_empresa', 'usuario__nombre']
    filterset_fields = ['id', 'usuario', 'nombre_empresa']

    def perform_create(self, serializer):
        # Asegurarse de que el usuario exista
        user = serializer.validated_data.get('usuario')
        if not user:
            raise serializers.ValidationError({'usuario': 'Este campo es requerido.'})
        serializer.save()


class SuscripcionViewSet(viewsets.ModelViewSet):
    queryset = Suscripcion.objects.all()
    serializer_class = SuscripcionSerializer
    permission_classes = [permissions.AllowAny]

class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]