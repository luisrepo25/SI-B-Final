from django.urls import path, include, re_path
from rest_framework import routers
from core.views import listar_suscripciones
from authz.api import RolViewSet
from .api import (
    CategoriaViewSet, ProveedorViewSet, ServicioViewSet, SuscripcionViewSet, UsuarioViewSet, CampaniaViewSet, PaqueteViewSet,
    CuponViewSet, ReservaViewSet, VisitanteViewSet, ReservaVisitanteViewSet,
    CampaniaServicioViewSet, PagoViewSet, ReglaReprogramacionViewSet,
    HistorialReprogramacionViewSet, ConfiguracionGlobalReprogramacionViewSet,
    ReprogramacionViewSet, TicketViewSet, TicketMessageViewSet, NotificacionViewSet,
    PerfilUsuarioViewSet, SoportePanelViewSet, FCMDeviceViewSet, CampanaNotificacionViewSet, ReservaMultiServicioView,
    PlanViewSet
)
from .api import BitacoraViewSet

# 🎤📊 Importar endpoints de reportes avanzados (CU19 y CU20)
from .views_reportes import (
    procesar_comando_ia,
    obtener_datos_graficas,
    generar_reporte_ventas,
    generar_reporte_clientes,
    generar_reporte_productos
)

router = routers.DefaultRouter()
router.register(r'categorias', CategoriaViewSet)
router.register(r'servicios', ServicioViewSet)
router.register(r'usuarios', UsuarioViewSet)
router.register(r'campanias', CampaniaViewSet)
router.register(r'paquetes', PaqueteViewSet, basename='paquete')
router.register(r'cupones', CuponViewSet)
router.register(r'reservas', ReservaViewSet)
router.register(r'visitantes', VisitanteViewSet)
router.register(r'reserva-visitantes', ReservaVisitanteViewSet)
router.register(r'campania-servicios', CampaniaServicioViewSet)
router.register(r'pagos', PagoViewSet)
router.register(r'reglas-reprogramacion', ReglaReprogramacionViewSet)
router.register(r'reprogramaciones', ReprogramacionViewSet)
router.register(r'rol', RolViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'ticket-messages', TicketMessageViewSet)
router.register(r'notificaciones', NotificacionViewSet)
router.register(r'fcm-dispositivos', FCMDeviceViewSet, basename='fcm-dispositivos')
router.register(r'campanas-notificacion', CampanaNotificacionViewSet, basename='campanas-notificacion')
router.register(r'historial-reprogramacion', HistorialReprogramacionViewSet)
router.register(r'configuracion-global-reprogramacion', ConfiguracionGlobalReprogramacionViewSet)
router.register(r'bitacora', BitacoraViewSet)
router.register(r'perfil', PerfilUsuarioViewSet, basename='perfil')
router.register(r'soporte-panel', SoportePanelViewSet, basename='soporte-panel')
router.register(r'proveedores', ProveedorViewSet, basename='proveedores')
router.register(r'suscripciones', SuscripcionViewSet, basename='suscripciones')
router.register(r'planes', PlanViewSet, basename='planes')


urlpatterns = router.urls + [
    path('backups/', include('condominio.backups.urls')),
    
    # 🎤 CU19: Reportes Avanzados con Comandos de Voz + IA
    path('reportes/ia/procesar/', procesar_comando_ia, name='procesar-comando-ia'),
    
    # 📊 CU20: API de Gráficas Interactivas
    path('reportes/graficas/', obtener_datos_graficas, name='obtener-datos-graficas'),
    
    # 📄 Generación de Reportes Descargables (PDF, Excel, DOCX)
    path("suscripciones/", listar_suscripciones),
    path('reportes/ventas/', generar_reporte_ventas, name='generar-reporte-ventas'),
    path('reportes/clientes/', generar_reporte_clientes, name='generar-reporte-clientes'),
    path('reportes/productos/', generar_reporte_productos, name='generar-reporte-productos'),
    # Aceptar con o sin barra final para evitar 404 en POST sin slash
    path('reservas-multiservicio/', ReservaMultiServicioView.as_view(), name='reserva-multiservicio'),
    re_path(r'^reservas-multiservicio/?$', ReservaMultiServicioView.as_view()),
]
