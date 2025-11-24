from typing import List, Dict, Any
import os
import logging
logger = logging.getLogger(__name__)

try:
    # Import opcional: solo si se va a enviar realmente
    from firebase_admin import messaging
    from .firebase import iniciar_firebase
    _HAS_FIREBASE = True
except Exception:
    messaging = None  # type: ignore
    iniciar_firebase = None  # type: ignore
    _HAS_FIREBASE = False


def enviar_tokens_push(tokens: List[Any], titulo: str, cuerpo: str, datos: Dict[str, str] | None = None) -> Dict[str, Any]:
    """Envía notificaciones a una lista de tokens usando firebase-admin.

    Comportamiento seguro para desarrollo:
    - Si la variable de entorno `SIMULAR_FCM` está activada, no intenta conectar con Firebase
      y devuelve una respuesta simulada (útil para pruebas locales).
    - Usa logging en lugar de prints.
    """
    simular = os.getenv('SIMULAR_FCM', '').lower() in ('1', 'true', 'si', 'yes')
    if simular:
        logger.info('SIMULACIÓN FCM: enviando a %d tokens', len(tokens))
        return {'success': len(tokens), 'failure': 0, 'responses': ['simulado' for _ in tokens]}

    if not _HAS_FIREBASE:
        logger.error('firebase-admin no está disponible en el entorno; exporta SIMULAR_FCM=1 para pruebas locales')
        return {'success': 0, 'failure': len(tokens), 'responses': ['firebase_not_installed' for _ in tokens]}

    try:
        app = iniciar_firebase()
    except Exception as e:
        logger.exception('No se pudo inicializar Firebase: %s', e)
        return {'success': 0, 'failure': len(tokens), 'responses': [str(e) for _ in tokens]}

    # tokens puede ser una lista de strings (tokens) o dicts {'token':..., 'tipo': 'android'|'ios'|'web'}
    mensajes = []
    token_map = []  # mantendremos el token asociado a cada mensaje para manejar respuestas
    for item in tokens:
        if isinstance(item, str):
            token = item
            tipo = None
        elif isinstance(item, dict):
            token = item.get('token') or item.get('registration_id')
            tipo = item.get('tipo') or item.get('tipo_dispositivo')
        else:
            # intentar acceder como tupla (token, tipo)
            try:
                token, tipo = item
            except Exception:
                logger.warning('Token en formato desconocido: %s', item)
                continue

        if not token:
            continue

        # Construir configuración por plataforma si es posible
        android_conf = None
        apns_conf = None
        if tipo and tipo.lower() == 'android' and _HAS_FIREBASE:
            try:
                android_conf = messaging.AndroidConfig(priority='high')
            except Exception:
                android_conf = None
        if tipo and tipo.lower() in ('ios', 'apns') and _HAS_FIREBASE:
            try:
                apns_conf = messaging.APNSConfig(headers={'apns-priority': '10'})
            except Exception:
                apns_conf = None

        msg = messaging.Message(
            token=token,
            notification=messaging.Notification(title=titulo, body=cuerpo) if _HAS_FIREBASE else None,
            data=datos or {},
            android=android_conf,
            apns=apns_conf,
        )
        mensajes.append(msg)
        token_map.append(token)

    if not mensajes:
        return {'success': 0, 'failure': 0, 'responses': []}

    try:
        if len(mensajes) == 1:
            resp = messaging.send(mensajes[0], app=app)
            return {'success': 1, 'failure': 0, 'responses': [str(resp)]}
        else:
            resp = messaging.send_all(mensajes, app=app)
            respuestas = []
            # procesar respuestas y marcar tokens inválidos si corresponde
            for idx, r in enumerate(resp.responses):
                token = token_map[idx] if idx < len(token_map) else None
                if r.exception:
                    respuestas.append(str(r.exception))
                    # marcaremos el token para revisión (devolveremos en responses); el caller puede limpiar
                    logger.warning('FCM error for token %s: %s', token, r.exception)
                    # Intentar marcar token inválido como inactivo si el error indica token no registrado
                    try:
                        err_str = str(r.exception).lower()
                        if token and any(x in err_str for x in ('registration-token-not-registered', 'invalid-registration-token', 'notregistered', 'not_registered')):
                            # Importar modelo de forma local para evitar import cycles
                            from condominio.models import FCMDevice
                            FCMDevice.objects.filter(registration_id=token).update(activo=False)
                            logger.info('Marcado token como inactivo: %s', token)
                    except Exception:
                        logger.exception('Error al marcar token inactivo %s', token)
                else:
                    respuestas.append('ok')
            return {
                'success': resp.success_count,
                'failure': resp.failure_count,
                'responses': respuestas
            }
    except Exception as e:
        logger.exception('Error al enviar mensajes FCM: %s', e)
        return {'success': 0, 'failure': len(mensajes), 'responses': [str(e) for _ in mensajes]}
