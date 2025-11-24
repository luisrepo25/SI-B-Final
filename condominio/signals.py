# condominio/signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.management import call_command
from django.apps import apps
import os
import logging
logger = logging.getLogger(__name__)


# Código existente para cargar fixtures está comentado; se mantiene.

# Importar señales FCM condicionalmente para evitar envíos automáticos por defecto.
# La variable de entorno en español 'HABILITAR_SEÑAL_FCM' controla esto.
fcm_var = os.getenv('HABILITAR_SEÑAL_FCM', '').strip().strip('"').strip("'").lower()
print(f'🔍 Verificando HABILITAR_SEÑAL_FCM: valor="{fcm_var}" (original: "{os.getenv("HABILITAR_SEÑAL_FCM", "")}")')

if fcm_var in ('1', 'true', 'si', 'yes'):
	try:
		import condominio.signals_fcm  # noqa: F401
		print(f'⚙️ Señales FCM activadas (HABILITAR_SEÑAL_FCM={fcm_var})')
		logger.info(f'⚙️ Señales FCM activadas (HABILITAR_SEÑAL_FCM={fcm_var})')
	except Exception as e:
		print(f'⚠️ No se pudo activar condominio.signals_fcm: {e}')
		logger.exception('⚠️ No se pudo activar condominio.signals_fcm: %s', e)
else:
	print(f'⚠️ Señales FCM NO activadas. HABILITAR_SEÑAL_FCM="{fcm_var}" (se esperaba: true, 1, si o yes)')
	logger.warning(f'⚠️ Señales FCM NO activadas. HABILITAR_SEÑAL_FCM="{fcm_var}" (se esperaba: true, 1, si o yes)')

