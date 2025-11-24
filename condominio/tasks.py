"""
Módulo de tareas para ejecución de campañas de notificaciones.

Este módulo contiene la lógica de negocio para ejecutar campañas de notificaciones,
separada de la API para facilitar su uso tanto en endpoints como en schedulers.
"""
import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


def ejecutar_campana_notificacion(campana_id, ejecutor_id=None):
    """
    Ejecuta una campaña de notificación, enviando notificaciones push a todos los usuarios objetivo.
    
    Esta función:
    1. Verifica que la campaña exista y pueda ejecutarse
    2. Obtiene la lista de usuarios objetivo según la segmentación
    3. Crea una notificación individual por cada usuario (dispara signals FCM automáticamente)
    4. Actualiza métricas y estado de la campaña
    
    Args:
        campana_id (int): ID de la campaña a ejecutar
        ejecutor_id (int, optional): ID del usuario que activó la campaña
    
    Returns:
        dict: Diccionario con resultado de la ejecución:
            - success (bool): Si la ejecución fue exitosa
            - total_enviados (int): Número de notificaciones enviadas
            - total_errores (int): Número de errores
            - mensaje (str): Mensaje descriptivo del resultado
    """
    from .models import CampanaNotificacion, Notificacion, Usuario
    
    try:
        campana = CampanaNotificacion.objects.get(id=campana_id)
    except CampanaNotificacion.DoesNotExist:
        error_msg = f'Campaña {campana_id} no encontrada'
        logger.error(error_msg)
        return {
            'success': False,
            'total_enviados': 0,
            'total_errores': 0,
            'mensaje': error_msg
        }
    
    # Verificar estado: si está cancelada, no ejecutar
    if campana.estado == 'CANCELADA':
        logger.info(f'Campaña {campana_id} ({campana.nombre}) está cancelada, no se ejecuta')
        return {
            'success': False,
            'total_enviados': 0,
            'total_errores': 0,
            'mensaje': 'Campaña cancelada'
        }
    
    # Si ya fue completada, no volver a ejecutar
    if campana.estado == 'COMPLETADA':
        logger.warning(f'Campaña {campana_id} ({campana.nombre}) ya fue completada')
        return {
            'success': False,
            'total_enviados': campana.total_enviados,
            'total_errores': campana.total_errores,
            'mensaje': 'Campaña ya fue ejecutada anteriormente'
        }
    
    logger.info(f'Iniciando ejecución de campaña {campana_id}: {campana.nombre}')
    
    # Marcar como en curso
    campana.estado = 'EN_CURSO'
    campana.save(update_fields=['estado'])
    
    # Obtener destinatarios
    usuarios = campana.obtener_usuarios_objetivo()
    total_usuarios = usuarios.count()
    
    logger.info(f'Campaña {campana_id}: {total_usuarios} usuarios objetivo identificados')
    
    total_enviados = 0
    total_errores = 0
    errores_detalle = []
    
    # Preparar datos de la notificación
    datos_notificacion = {
        'titulo': campana.titulo,
        'mensaje': campana.cuerpo,
        'campana_id': str(campana.id),
        'campana_nombre': campana.nombre,
    }
    
    # Agregar datos extra si existen
    if campana.datos_extra:
        datos_notificacion.update(campana.datos_extra)
    
    # Crear notificaciones individualmente
    # Cada creación dispara automáticamente el signal que envía FCM
    for usuario in usuarios:
        try:
            # Usar transaction.atomic para asegurar integridad
            with transaction.atomic():
                Notificacion.objects.create(
                    usuario=usuario,
                    tipo=campana.tipo_notificacion,
                    datos=datos_notificacion,
                    leida=False
                )
            total_enviados += 1
            
            # Log cada 50 usuarios para monitoreo
            if total_enviados % 50 == 0:
                logger.info(f'Campaña {campana_id}: {total_enviados}/{total_usuarios} notificaciones enviadas')
                
        except Exception as e:
            total_errores += 1
            error_msg = f'Usuario {usuario.id} ({usuario.nombre}): {str(e)}'
            errores_detalle.append(error_msg)
            logger.exception(f'Error enviando notificación a usuario {usuario.id} en campaña {campana_id}: {e}')
            
            # Si hay muchos errores consecutivos, considerar detener
            if total_errores > 100 and total_enviados == 0:
                logger.error(f'Campaña {campana_id}: Demasiados errores, deteniendo ejecución')
                break
    
    # Actualizar métricas y estado final
    campana.estado = 'COMPLETADA'
    campana.fecha_enviada = timezone.now()
    campana.total_enviados = total_enviados
    campana.total_errores = total_errores
    campana.total_destinatarios = total_usuarios  # Actualizar con el valor real
    
    if ejecutor_id:
        try:
            campana.enviado_por_id = ejecutor_id
        except Exception:
            logger.warning(f'No se pudo asignar ejecutor {ejecutor_id} a campaña {campana_id}')
    
    campana.save()
    
    # Log final
    logger.info(
        f'Campaña {campana_id} ({campana.nombre}) completada: '
        f'{total_enviados} enviados exitosamente, '
        f'{total_errores} errores de {total_usuarios} usuarios objetivo'
    )
    
    if errores_detalle and len(errores_detalle) <= 10:
        logger.warning(f'Errores en campaña {campana_id}: {errores_detalle}')
    
    return {
        'success': True,
        'total_enviados': total_enviados,
        'total_errores': total_errores,
        'total_destinatarios': total_usuarios,
        'mensaje': f'Campaña ejecutada: {total_enviados} enviados, {total_errores} errores'
    }


def enviar_notificacion_test(campana_id, usuario_id):
    """
    Envía una notificación de prueba de una campaña a un usuario específico.
    
    Útil para que administradores prueben cómo se verá la notificación
    antes de activar la campaña completa.
    
    Args:
        campana_id (int): ID de la campaña
        usuario_id (int): ID del usuario destinatario del test
    
    Returns:
        dict: Resultado del envío de prueba
    """
    from .models import CampanaNotificacion, Notificacion, Usuario
    
    try:
        campana = CampanaNotificacion.objects.get(id=campana_id)
        usuario = Usuario.objects.get(id=usuario_id)
    except CampanaNotificacion.DoesNotExist:
        return {'success': False, 'mensaje': 'Campaña no encontrada'}
    except Usuario.DoesNotExist:
        return {'success': False, 'mensaje': 'Usuario no encontrado'}
    
    try:
        # Preparar datos con prefijo [TEST]
        datos_test = {
            'titulo': f"[TEST] {campana.titulo}",
            'mensaje': campana.cuerpo,
            'campana_id': str(campana.id),
            'campana_nombre': campana.nombre,
            'es_test': True,
        }
        
        if campana.datos_extra:
            datos_test.update(campana.datos_extra)
        
        # Crear notificación de prueba
        notif = Notificacion.objects.create(
            usuario=usuario,
            tipo=campana.tipo_notificacion,
            datos=datos_test
        )
        
        logger.info(
            f'Notificación de prueba enviada: campaña {campana_id} '
            f'({campana.nombre}) -> usuario {usuario_id} ({usuario.nombre})'
        )
        
        return {
            'success': True,
            'notificacion_id': notif.id,
            'mensaje': f'Notificación de prueba enviada a {usuario.nombre}'
        }
        
    except Exception as e:
        logger.exception(f'Error enviando notificación de prueba: {e}')
        return {
            'success': False,
            'mensaje': f'Error al enviar prueba: {str(e)}'
        }


def calcular_metricas_campana(campana_id):
    """
    Recalcula las métricas de una campaña contando notificaciones leídas.
    
    Útil para actualizar estadísticas después de que la campaña fue enviada.
    
    Args:
        campana_id (int): ID de la campaña
    
    Returns:
        dict: Métricas actualizadas
    """
    from .models import CampanaNotificacion, Notificacion
    
    try:
        campana = CampanaNotificacion.objects.get(id=campana_id)
    except CampanaNotificacion.DoesNotExist:
        return {'success': False, 'mensaje': 'Campaña no encontrada'}
    
    if campana.estado != 'COMPLETADA':
        return {'success': False, 'mensaje': 'La campaña no está completada'}
    
    try:
        # Contar notificaciones leídas de esta campaña
        notificaciones_leidas = Notificacion.objects.filter(
            datos__campana_id=str(campana.id),
            leida=True
        ).count()
        
        campana.total_leidos = notificaciones_leidas
        campana.save(update_fields=['total_leidos'])
        
        porcentaje_lectura = (
            (notificaciones_leidas / campana.total_enviados * 100)
            if campana.total_enviados > 0 else 0
        )
        
        logger.info(
            f'Métricas actualizadas para campaña {campana_id}: '
            f'{notificaciones_leidas} leídas de {campana.total_enviados} enviadas '
            f'({porcentaje_lectura:.1f}%)'
        )
        
        return {
            'success': True,
            'total_leidos': notificaciones_leidas,
            'total_enviados': campana.total_enviados,
            'porcentaje_lectura': round(porcentaje_lectura, 2)
        }
        
    except Exception as e:
        logger.exception(f'Error calculando métricas de campaña {campana_id}: {e}')
        return {'success': False, 'mensaje': str(e)}
