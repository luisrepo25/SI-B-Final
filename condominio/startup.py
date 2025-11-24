import os
import logging

logger = logging.getLogger(__name__)

def initialize_backups():
    """Inicializa los backups automáticos - método alternativo para producción"""
    try:
        # Verificar si ya se inició (evitar duplicados)
        if not hasattr(initialize_backups, '_executed'):
            initialize_backups._executed = True
            
            if os.environ.get('ENABLE_AUTOMATIC_BACKUPS') == 'true':
                from condominio.backups.backup_tool import start_automatic_backups
                start_automatic_backups()
                logger.info("🤖 Backups automáticos iniciados desde startup.py")
            else:
                logger.info("🔇 Backups automáticos desactivados")
    except Exception as e:
        logger.error(f"❌ Error iniciando backups: {e}")

# Ejecutar al importar
initialize_backups()