import os
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notificacion, FCMDevice
from core.notifications import enviar_tokens_push

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notificacion)
def notificacion_post_save_fcm(sender, instance, created, **kwargs):
    """Envía notificación push vía FCM cuando se crea una Notificacion.

    Esta señal solo será importada/activada si la variable de entorno
    `HABILITAR_SEÑAL_FCM` está presente y no es falsey.
    """
    if not created:
        return

    try:
        # recolectar tokens activos del usuario destinatario (traer tipo_dispositivo)
        dispositivos = FCMDevice.objects.filter(usuario=instance.usuario, activo=True)
        tokens = []
        for d in dispositivos:
            tokens.append({'token': d.registration_id, 'tipo': d.tipo_dispositivo})
        if not tokens:
            logger.warning(f'Usuario {instance.usuario.id} ({instance.usuario.nombre}) no tiene dispositivos FCM activos')
            return

        # Preparar contenido de la notificación
        titulo = 'Nueva notificación'  # Default
        cuerpo = None
        datos_extra = {'notificacion_id': str(instance.id)}

        # Si en `datos` hay un campo `mensaje`, usarlo
        if isinstance(instance.datos, dict):
            # ✅ CORRECCIÓN: Usar título de la campaña si existe
            titulo = instance.datos.get('titulo', titulo)
            cuerpo = instance.datos.get('mensaje') or instance.datos.get('body')
            # exportar el objeto datos como string si existe
            datos_extra.update({k: str(v) for k, v in instance.datos.items()})

        if not cuerpo:
            cuerpo = f'Tienes una notificación de tipo: {instance.tipo}'

        # Enviar
        resp = enviar_tokens_push(tokens, titulo, cuerpo, datos_extra)
        logger.info(f'✅ FCM enviado para Notificacion {instance.id} (Usuario: {instance.usuario.nombre}): {resp}')
    except Exception as e:
        logger.exception(f'❌ Error al enviar FCM para Notificacion {instance.id}: {e}')
