#!/usr/bin/env python
"""
🎯 GENERAR RECOMENDACIÓN PARA SESSION_ID ESPECÍFICO
===================================================

Este script genera una recomendación para el session_id
que está intentando consultar la app de Flutter.

Session ID: cs_test_a1Kqx1wJULrrg2DK1RFqMQgQsamwUr4ksaghA9auRng0EmDpafVGNh8IUl
Reserva ID: 1864
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.cache import cache
from core.webhooks import generate_and_cache_recommendation

# Datos del log de Flutter
SESSION_ID = "cs_test_a1Kqx1wJULrrg2DK1RFqMQgQsamwUr4ksaghA9auRng0EmDpafVGNh8IUl"
RESERVA_ID = 1864

print("="*70)
print("🎯 GENERANDO RECOMENDACIÓN PARA FLUTTER APP")
print("="*70)
print(f"\nSession ID: {SESSION_ID}")
print(f"Reserva ID: {RESERVA_ID}")

# Limpiar cache previo
cache_key = f'recommendation_{SESSION_ID}'
cache.delete(cache_key)
print(f"\n🧹 Cache limpiado: {cache_key[:60]}...")

# Generar
print("\n🔄 Generando recomendación...")
import time
inicio = time.time()

try:
    generate_and_cache_recommendation(RESERVA_ID, SESSION_ID)
    tiempo = time.time() - inicio
    
    print(f"✅ Generación completada en {tiempo:.2f} segundos")
    
    # Verificar
    cached = cache.get(cache_key)
    if cached:
        print("\n✅ RECOMENDACIÓN EN CACHE")
        print(f"   Estado: {cached.get('estado', 'N/A')}")
        
        if cached.get('estado') == 'OK':
            recom = cached.get('recomendacion', {})
            print(f"   Texto: {recom.get('texto', '')[:80]}...")
            print(f"   Categorías: {len(recom.get('items', []))}")
            
            print("\n📱 LA APP FLUTTER AHORA PUEDE OBTENERLA")
            print(f"   GET /api/recomendacion/?session_id={SESSION_ID}")
            
        elif cached.get('estado') == 'ERROR':
            print(f"   ❌ Error: {cached.get('error', 'N/A')}")
    else:
        print("\n❌ NO SE GUARDÓ EN CACHE")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
