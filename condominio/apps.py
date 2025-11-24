from django.apps import AppConfig

class CondominioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'condominio'

    def ready(self):
        # Importar y registrar señales
        import condominio.signals
        
        # Inicializar Firebase al arrancar Django
        self.initialize_firebase()
        
        # Iniciar el programador de backups automáticos (SOLO UNA VEZ)
        self.start_automatic_backups()
        
        # ⚠️ DESHABILITADO: El scheduler ahora corre como comando separado en Procfile
        # self.start_campaign_scheduler()

    def initialize_firebase(self):
        """
        Inicializa Firebase Admin SDK al arrancar Django.
        Solo se ejecuta una vez usando un flag.
        """
        if not hasattr(self, '_firebase_initialized'):
            self._firebase_initialized = True
            
            try:
                from core.firebase import iniciar_firebase
                app = iniciar_firebase()
                print(f"✅ Firebase Admin inicializado correctamente: {app.name}")
            except Exception as e:
                print(f"⚠️ Error al inicializar Firebase: {e}")
                print("   Las notificaciones push NO funcionarán hasta que se configure correctamente.")

    def start_automatic_backups(self):  # ✅ DENTRO de la clase
        """
        Inicia el programador de backups automáticos una sola vez
        """
        if not hasattr(self, '_backup_scheduler_started'):
            self._backup_scheduler_started = True
            
            import os
            print("🎯 APPS.PY - ENABLE_AUTOMATIC_BACKUPS =", os.environ.get('ENABLE_AUTOMATIC_BACKUPS'))
            
            if os.environ.get('ENABLE_AUTOMATIC_BACKUPS') == 'true':
                try:
                    from condominio.backups.backup_tool import start_automatic_backups
                    print("🎯 APPS.PY - Iniciando scheduler...")
                    start_automatic_backups()
                    print("🎯 APPS.PY - Scheduler iniciado")
                except Exception as e:
                    print(f"🎯 APPS.PY - Error: {e}")

    def start_campaign_scheduler(self):
        """
        Inicia el programador de campañas programadas una sola vez
        SOLO en el proceso principal (no en workers de Gunicorn)
        """
        if not hasattr(self, '_campaign_scheduler_started'):
            self._campaign_scheduler_started = True
            
            import os
            # Solo ejecutar en el proceso principal (PID bajo o variable de entorno específica)
            worker_id = os.environ.get('GUNICORN_WORKER_ID')
            
            if worker_id:
                # Estamos en un worker de Gunicorn, no iniciar scheduler
                print(f"⏸️ Worker {worker_id}: Scheduler NO iniciado (solo corre en proceso principal)")
                return
            
            try:
                from condominio.scheduler_campanas import start_campaign_scheduler
                start_campaign_scheduler()
            except Exception as e:
                print(f"⚠️ Error al iniciar scheduler de campañas: {e}")
                print("   Las campañas programadas NO se ejecutarán automáticamente.")