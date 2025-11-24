#!/usr/bin/env python
"""
Script para sincronizar migraciones en Railway cuando hay conflictos.
Se ejecuta antes de migrate en el Procfile.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

def check_table_exists(table_name):
    """Verifica si una tabla existe en la base de datos."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]

def check_migration_applied(app_name, migration_name):
    """Verifica si una migración ya está registrada en django_migrations."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM django_migrations 
                WHERE app = %s AND name = %s
            );
        """, [app_name, migration_name])
        return cursor.fetchone()[0]

def main():
    print("🔍 Verificando estado de migraciones...")
    
    # Lista de tablas y sus migraciones correspondientes
    checks = [
        ('condominio_fcmdevice', 'condominio', '0006_fcmdevice'),
        ('condominio_campananotificacion', 'condominio', '0007_alter_notificacion_tipo_campananotificacion'),
    ]
    
    for table_name, app_name, migration_name in checks:
        table_exists = check_table_exists(table_name)
        migration_applied = check_migration_applied(app_name, migration_name)
        
        if table_exists and not migration_applied:
            print(f"⚠️  Tabla '{table_name}' existe pero migración '{migration_name}' no está registrada")
            print(f"🔧 Aplicando fake migration para '{migration_name}'...")
            call_command('migrate', app_name, migration_name, '--fake', verbosity=0)
            print(f"✅ Migración '{migration_name}' sincronizada")
        elif table_exists and migration_applied:
            print(f"✅ Tabla '{table_name}' y migración '{migration_name}' están sincronizadas")
    
    print("✅ Verificación de migraciones completada")

if __name__ == '__main__':
    main()
