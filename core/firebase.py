import os
import json
import base64
import firebase_admin
from firebase_admin import credentials


def iniciar_firebase():
    """Inicializa y devuelve la app firebase_admin.

    Soporta tres modos:
    1. Base64 (RECOMENDADO para producción): FIREBASE_CREDENTIALS_BASE64
    2. JSON directo (Railway/Heroku): FIREBASE_CREDENTIALS_JSON
    3. Archivo local (desarrollo): RUTA_CUENTA_SERVICIO_FIREBASE
    """
    # Evitar reinicializar si ya está inicializada
    if firebase_admin._apps:
        return firebase_admin.get_app()

    # Modo 1: Base64 (RECOMENDADO - evita problemas con escapes)
    base64_content = os.getenv('FIREBASE_CREDENTIALS_BASE64')
    if base64_content:
        try:
            # Decodificar Base64
            json_content = base64.b64decode(base64_content).decode('utf-8')
            cred_dict = json.loads(json_content)
            cred = credentials.Certificate(cred_dict)
            app = firebase_admin.initialize_app(cred)
            return app
        except Exception as e:
            raise RuntimeError(f'Error al parsear FIREBASE_CREDENTIALS_BASE64: {e}')

    # Modo 2: JSON directo (puede tener problemas con escapes)
    json_content = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if json_content:
        try:
            cred_dict = json.loads(json_content)
            cred = credentials.Certificate(cred_dict)
            app = firebase_admin.initialize_app(cred)
            return app
        except json.JSONDecodeError as e:
            raise RuntimeError(f'Error al parsear FIREBASE_CREDENTIALS_JSON: {e}')
    
    # Modo 3: Archivo local (DESARROLLO)
    ruta = os.getenv('RUTA_CUENTA_SERVICIO_FIREBASE') or os.getenv('FIREBASE_SERVICE_ACCOUNT')
    if ruta:
        if not os.path.exists(ruta):
            raise RuntimeError(f'El archivo de credenciales no existe: {ruta}')
        cred = credentials.Certificate(ruta)
        app = firebase_admin.initialize_app(cred)
        return app
    
    # Si no hay ninguna configuración
    raise RuntimeError(
        'No se encontró configuración de Firebase. Configura una de estas variables:\n'
        '  - FIREBASE_CREDENTIALS_BASE64 (recomendado para producción)\n'
        '  - FIREBASE_CREDENTIALS_JSON (alternativa para producción)\n'
        '  - RUTA_CUENTA_SERVICIO_FIREBASE (para desarrollo local)'
    )
