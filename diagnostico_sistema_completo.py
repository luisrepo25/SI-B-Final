#!/usr/bin/env python
"""
🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA DE RECOMENDACIONES
======================================================

Este script verifica TODOS los componentes del sistema:
1. Base de datos (Reserva y session_id)
2. Cache (Django cache funcionando)
3. Generación de IA (Groq API)
4. Endpoint (obtener_recomendacion)
5. Variables de entorno

Fecha: 4 de noviembre, 2025
"""

import os
import sys
import django
import json
import time

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.cache import cache
from django.conf import settings
from condominio.models import Reserva
from core.ai import generate_and_cache_recommendation


class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def print_header(texto):
    print(f"\n{Color.BOLD}{Color.BLUE}{'='*70}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.BLUE}{texto.center(70)}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.BLUE}{'='*70}{Color.ENDC}\n")


def print_success(texto):
    print(f"{Color.GREEN}✅ {texto}{Color.ENDC}")


def print_error(texto):
    print(f"{Color.RED}❌ {texto}{Color.ENDC}")


def print_warning(texto):
    print(f"{Color.YELLOW}⚠️  {texto}{Color.ENDC}")


def print_info(texto):
    print(f"{Color.CYAN}ℹ️  {texto}{Color.ENDC}")


def print_section(titulo):
    print(f"\n{Color.BOLD}{Color.CYAN}{'▶ ' + titulo}{Color.ENDC}")
    print(f"{Color.CYAN}{'-'*70}{Color.ENDC}")


def diagnostico_completo():
    """Ejecuta diagnóstico completo del sistema"""
    
    print_header("🔍 DIAGNÓSTICO DEL SISTEMA DE RECOMENDACIONES")
    
    problemas = []
    warnings = []
    
    # ============================================
    # 1. VERIFICAR VARIABLES DE ENTORNO
    # ============================================
    print_section("1. VARIABLES DE ENTORNO")
    
    # Groq API Key
    groq_key = os.getenv('GROQ_API_KEY', '')
    if groq_key and groq_key.startswith('gsk_'):
        print_success(f"GROQ_API_KEY configurada: {groq_key[:20]}...")
    else:
        print_error("GROQ_API_KEY NO configurada o inválida")
        problemas.append("GROQ_API_KEY faltante o incorrecta")
    
    # Stripe Webhook Secret
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    if webhook_secret and webhook_secret.startswith('whsec_'):
        print_success(f"STRIPE_WEBHOOK_SECRET configurada: {webhook_secret[:20]}...")
    else:
        print_error("STRIPE_WEBHOOK_SECRET NO configurada o inválida")
        problemas.append("STRIPE_WEBHOOK_SECRET faltante o incorrecta")
    
    # Stripe API Key
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if stripe_key and (stripe_key.startswith('sk_test_') or stripe_key.startswith('sk_live_')):
        print_success(f"STRIPE_SECRET_KEY configurada: {stripe_key[:15]}...")
    else:
        print_error("STRIPE_SECRET_KEY NO configurada o inválida")
        problemas.append("STRIPE_SECRET_KEY faltante o incorrecta")
    
    # ============================================
    # 2. VERIFICAR BASE DE DATOS
    # ============================================
    print_section("2. BASE DE DATOS - Reservas con session_id")
    
    # Buscar la reserva del diagnóstico
    try:
        reserva_1864 = Reserva.objects.filter(id=1864).first()
        if reserva_1864:
            print_success(f"Reserva #1864 encontrada")
            print_info(f"   Estado: {reserva_1864.estado}")
            print_info(f"   Cliente: {reserva_1864.cliente.nombre}")
            print_info(f"   Total: {reserva_1864.total} {reserva_1864.moneda}")
            print_info(f"   Fecha: {reserva_1864.fecha}")
            
            # Verificar si tiene paquete o servicio
            if reserva_1864.paquete:
                print_info(f"   Paquete: {reserva_1864.paquete.nombre}")
            elif reserva_1864.servicio:
                print_info(f"   Servicio: {reserva_1864.servicio.titulo}")
            else:
                print_warning("   Sin paquete ni servicio asociado")
                warnings.append("Reserva #1864 sin paquete/servicio")
        else:
            print_warning("Reserva #1864 no encontrada")
            warnings.append("Reserva #1864 no existe")
    except Exception as e:
        print_error(f"Error al consultar reserva: {e}")
        problemas.append(f"Error BD: {str(e)}")
    
    # Buscar cualquier reserva válida para prueba
    try:
        reserva_test = Reserva.objects.filter(paquete__isnull=False).first()
        if not reserva_test:
            reserva_test = Reserva.objects.filter(servicio__isnull=False).first()
        
        if reserva_test:
            print_success(f"Reserva de prueba encontrada: #{reserva_test.id}")
            test_reserva_id = reserva_test.id
        else:
            print_error("No hay reservas válidas para prueba")
            problemas.append("No hay reservas con paquete/servicio")
            test_reserva_id = None
    except Exception as e:
        print_error(f"Error buscando reservas: {e}")
        problemas.append(f"Error BD: {str(e)}")
        test_reserva_id = None
    
    # ============================================
    # 3. VERIFICAR CACHE
    # ============================================
    print_section("3. DJANGO CACHE")
    
    test_key = 'diagnostico_test'
    test_value = {'test': 'OK', 'timestamp': time.time()}
    
    try:
        # Probar set
        cache.set(test_key, test_value, timeout=60)
        print_success("Cache SET funcionando")
        
        # Probar get
        retrieved = cache.get(test_key)
        if retrieved and retrieved.get('test') == 'OK':
            print_success("Cache GET funcionando")
            print_info(f"   Backend de cache: {settings.CACHES['default']['BACKEND']}")
        else:
            print_error("Cache GET falló")
            problemas.append("Cache GET no funciona")
        
        # Limpiar
        cache.delete(test_key)
        print_success("Cache DELETE funcionando")
        
    except Exception as e:
        print_error(f"Error en cache: {e}")
        problemas.append(f"Cache error: {str(e)}")
    
    # ============================================
    # 4. VERIFICAR CACHE DEL SESSION_ID REAL
    # ============================================
    print_section("4. VERIFICAR CACHE CON SESSION_ID REAL")
    
    session_id_real = "cs_test_a1Kqx1wJULrrg2DK1RFqMQgQsamwUr4ksaghA9auRng0EmDpafVGNh8IUl"
    cache_key_real = f'recommendation_{session_id_real}'
    
    print_info(f"Session ID: {session_id_real}")
    print_info(f"Cache key: {cache_key_real[:60]}...")
    
    cached_recommendation = cache.get(cache_key_real)
    if cached_recommendation:
        print_success("¡Recomendación encontrada en cache!")
        print_info(f"   Estado: {cached_recommendation.get('estado', 'N/A')}")
        if cached_recommendation.get('estado') == 'OK':
            recom = cached_recommendation.get('recomendacion', {})
            print_info(f"   Texto: {recom.get('texto', '')[:50]}...")
            print_info(f"   Categorías: {len(recom.get('items', []))}")
        elif cached_recommendation.get('estado') == 'ERROR':
            print_error(f"   Error: {cached_recommendation.get('error', 'N/A')}")
    else:
        print_warning("No hay recomendación en cache para este session_id")
        print_info("Esto es NORMAL si aún no se ha hecho un pago con este session_id")
        warnings.append(f"No hay recomendación en cache para {session_id_real[:40]}...")
    
    # ============================================
    # 5. GENERAR RECOMENDACIÓN DE PRUEBA
    # ============================================
    print_section("5. GENERACIÓN DE RECOMENDACIÓN CON IA")
    
    if test_reserva_id and groq_key.startswith('gsk_'):
        print_info(f"Generando recomendación para reserva #{test_reserva_id}...")
        
        # Generar session_id de prueba
        import random
        import string
        test_session_id = 'cs_test_' + ''.join(random.choices(string.ascii_letters + string.digits, k=60))
        
        print_info(f"Session ID de prueba: {test_session_id[:50]}...")
        
        try:
            inicio = time.time()
            generate_and_cache_recommendation(test_reserva_id, test_session_id)
            tiempo = time.time() - inicio
            
            print_success(f"Generación completada en {tiempo:.2f} segundos")
            
            # Verificar que se guardó
            test_cache_key = f'recommendation_{test_session_id}'
            test_cached = cache.get(test_cache_key)
            
            if test_cached:
                print_success("✓ Recomendación guardada en cache")
                
                if test_cached.get('estado') == 'OK':
                    print_success("✓ Estado: OK")
                    recom = test_cached.get('recomendacion', {})
                    print_info(f"   Texto: {recom.get('texto', '')[:60]}...")
                    print_info(f"   Categorías: {len(recom.get('items', []))}")
                elif test_cached.get('estado') == 'ERROR':
                    print_error(f"✗ Error: {test_cached.get('error', 'N/A')}")
                    problemas.append(f"Error en generación IA: {test_cached.get('error', 'N/A')}")
            else:
                print_error("✗ No se guardó en cache")
                problemas.append("Recomendación no se guardó en cache")
                
        except Exception as e:
            print_error(f"Error generando recomendación: {e}")
            problemas.append(f"Error generación IA: {str(e)}")
            import traceback
            print(f"\n{Color.RED}{traceback.format_exc()}{Color.ENDC}")
    else:
        if not test_reserva_id:
            print_warning("No se puede probar generación (no hay reserva de prueba)")
        if not groq_key.startswith('gsk_'):
            print_warning("No se puede probar generación (GROQ_API_KEY no configurada)")
    
    # ============================================
    # 6. VERIFICAR ENDPOINT
    # ============================================
    print_section("6. ENDPOINT DE RECOMENDACIÓN")
    
    print_info("Endpoint: GET /api/recomendacion/?session_id=XXX")
    
    # Verificar que la URL está registrada
    try:
        from django.urls import get_resolver
        from django.urls.resolvers import URLPattern, URLResolver
        
        resolver = get_resolver()
        
        def find_patterns(patterns, prefix=''):
            found = []
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    found.extend(find_patterns(pattern.url_patterns, prefix + str(pattern.pattern)))
                elif isinstance(pattern, URLPattern):
                    url = prefix + str(pattern.pattern)
                    if 'recomendacion' in url:
                        found.append(url)
            return found
        
        urls_recomendacion = find_patterns(resolver.url_patterns)
        
        if urls_recomendacion:
            print_success("Endpoint registrado en urls.py")
            for url in urls_recomendacion:
                print_info(f"   {url}")
        else:
            print_error("Endpoint NO encontrado en urls.py")
            problemas.append("Endpoint /api/recomendacion/ no registrado")
            
    except Exception as e:
        print_warning(f"No se pudo verificar URLs: {e}")
    
    # ============================================
    # 7. GENERAR RECOMENDACIÓN PARA SESSION_ID REAL
    # ============================================
    print_section("7. GENERAR RECOMENDACIÓN PARA SESSION_ID DEL LOG")
    
    if not cached_recommendation and test_reserva_id:
        print_info("Generando recomendación para el session_id del log de Flutter...")
        print_info(f"Session ID: {session_id_real}")
        print_info(f"Reserva: #{1864 if reserva_1864 else test_reserva_id}")
        
        try:
            reserva_para_generar = 1864 if reserva_1864 else test_reserva_id
            inicio = time.time()
            generate_and_cache_recommendation(reserva_para_generar, session_id_real)
            tiempo = time.time() - inicio
            
            print_success(f"Generación completada en {tiempo:.2f} segundos")
            
            # Verificar
            cached_now = cache.get(cache_key_real)
            if cached_now:
                print_success("✓ Ahora está en cache")
                print_info("✓ La app Flutter debería poder obtenerla ahora")
                
                if cached_now.get('estado') == 'OK':
                    print_success("✓ Estado: OK")
                elif cached_now.get('estado') == 'ERROR':
                    print_error(f"✗ Error: {cached_now.get('error', 'N/A')}")
            else:
                print_error("✗ Aún no está en cache")
                problemas.append("No se pudo guardar en cache")
                
        except Exception as e:
            print_error(f"Error: {e}")
            problemas.append(f"Error generando para session_id real: {str(e)}")
    
    # ============================================
    # RESUMEN FINAL
    # ============================================
    print_header("📊 RESUMEN DEL DIAGNÓSTICO")
    
    if not problemas and not warnings:
        print(f"{Color.GREEN}{Color.BOLD}✅ ¡SISTEMA FUNCIONANDO CORRECTAMENTE!{Color.ENDC}\n")
        print_success("Todos los componentes están operativos")
        print_success("El problema es el webhook de Stripe (no configurado)")
        
        print(f"\n{Color.BOLD}SOLUCIÓN:{Color.ENDC}")
        print("1. Configurar webhook en Stripe Dashboard")
        print("2. URL: https://backendspring2-production.up.railway.app/webhooks/stripe/")
        print("3. Evento: checkout.session.completed")
        print("4. Copiar Signing Secret a Railway como STRIPE_WEBHOOK_SECRET")
        
    elif problemas:
        print(f"{Color.RED}{Color.BOLD}❌ PROBLEMAS ENCONTRADOS ({len(problemas)}){Color.ENDC}\n")
        for i, problema in enumerate(problemas, 1):
            print(f"{Color.RED}  {i}. {problema}{Color.ENDC}")
        
        print(f"\n{Color.BOLD}SOLUCIONAR EN ORDEN:{Color.ENDC}")
        if any('GROQ' in p for p in problemas):
            print("1️⃣  Configurar GROQ_API_KEY en Railway")
        if any('STRIPE' in p for p in problemas):
            print("2️⃣  Configurar variables de Stripe en Railway")
        if any('Cache' in p for p in problemas):
            print("3️⃣  Verificar configuración de cache (Redis/Memcached)")
        if any('BD' in p for p in problemas):
            print("4️⃣  Verificar conexión a base de datos")
    
    if warnings:
        print(f"\n{Color.YELLOW}{Color.BOLD}⚠️  ADVERTENCIAS ({len(warnings)}){Color.ENDC}\n")
        for i, warning in enumerate(warnings, 1):
            print(f"{Color.YELLOW}  {i}. {warning}{Color.ENDC}")
    
    # Información adicional
    print(f"\n{Color.BOLD}PRÓXIMOS PASOS:{Color.ENDC}")
    print("1. Desplegar a Railway (si aún no está desplegado)")
    print("2. Configurar webhook en Stripe Dashboard")
    print("3. Hacer pago de prueba desde Flutter")
    print("4. Verificar logs en Railway con: railway logs")
    
    print(f"\n{Color.BOLD}LOGS A BUSCAR EN RAILWAY:{Color.ENDC}")
    print('  railway logs | grep "Webhook recibido"')
    print('  railway logs | grep "Generando recomendación"')
    print('  railway logs | grep "guardada en cache"')
    
    print("\n" + "="*70)
    print(f"{Color.BOLD}  🔍 DIAGNÓSTICO COMPLETADO{Color.ENDC}")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        diagnostico_completo()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Diagnóstico interrumpido{Color.ENDC}")
    except Exception as e:
        print(f"\n{Color.RED}❌ Error fatal: {str(e)}{Color.ENDC}")
        import traceback
        traceback.print_exc()
