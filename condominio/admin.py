from django.contrib import admin
from .models import (
    Usuario, Categoria, Campania, Cupon, Reserva, Visitante, ReservaVisitante,
    Servicio, Paquete, PaqueteServicio, CampaniaServicio, Pago, Reprogramacion,
    Ticket, TicketMessage, Notificacion, Bitacora, ComprobantePago,
    ReglaReprogramacion, HistorialReprogramacion,
    ConfiguracionGlobalReprogramacion, FCMDevice, CampanaNotificacion
)

# =====================================================
# � DISPOSITIVOS FCM
# =====================================================
@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    """Administración de dispositivos FCM."""
    list_display = ['id', 'usuario', 'tipo_dispositivo', 'nombre', 'activo', 'ultima_vez']
    list_filter = ['tipo_dispositivo', 'activo', 'created_at']
    search_fields = ['usuario__nombre', 'registration_id', 'nombre']
    readonly_fields = ['registration_id', 'created_at', 'ultima_vez']
    
    fieldsets = (
        ('Información del Dispositivo', {
            'fields': ('usuario', 'registration_id', 'tipo_dispositivo', 'nombre', 'activo')
        }),
        ('Fechas', {
            'fields': ('created_at', 'ultima_vez'),
            'classes': ('collapse',)
        }),
    )


# =====================================================
# 📢 CAMPAÑA DE NOTIFICACIONES
# =====================================================
@admin.register(CampanaNotificacion)
class CampanaNotificacionAdmin(admin.ModelAdmin):
    """Administración de campañas de notificaciones en Django Admin."""
    list_display = [
        'id', 'nombre', 'estado', 'tipo_audiencia', 
        'total_destinatarios', 'total_enviados', 'total_errores',
        'fecha_programada', 'fecha_enviada', 'created_at'
    ]
    list_filter = ['estado', 'tipo_audiencia', 'tipo_notificacion', 'created_at']
    search_fields = ['nombre', 'titulo', 'descripcion']
    readonly_fields = [
        'estado', 'fecha_enviada',
        'total_destinatarios', 'total_enviados', 'total_errores',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'descripcion', 'estado')
        }),
        ('Contenido de la Notificación', {
            'fields': ('titulo', 'cuerpo', 'tipo_notificacion', 'datos_extra')
        }),
        ('Audiencia y Segmentación', {
            'fields': ('tipo_audiencia', 'usuarios_objetivo', 'segmento_filtros')
        }),
        ('Programación', {
            'fields': ('fecha_programada', 'enviar_inmediatamente')
        }),
        ('Métricas', {
            'fields': ('total_destinatarios', 'total_enviados', 'total_errores'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Registrar otros modelos (ejemplo básico)
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'rol', 'num_viajes', 'created_at']
    search_fields = ['nombre', 'user__email']
    list_filter = ['rol', 'created_at']


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'tipo', 'leida', 'created_at']
    list_filter = ['tipo', 'leida', 'created_at']
    search_fields = ['usuario__nombre']
    readonly_fields = ['created_at']





@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'accion', 'ip_address', 'created_at']
    list_filter = ['created_at']
    search_fields = ['usuario__nombre', 'accion', 'descripcion']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
