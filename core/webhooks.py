# core/webhooks.py
import stripe
from threading import Thread
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache
from .ai import generate_packing_recommendation

stripe.api_key = settings.STRIPE_SECRET_KEY

def generate_and_cache_recommendation(reserva_id: int, session_id: str):
    """
    Genera la recomendación en background y la guarda en cache.
    
    Args:
        reserva_id: ID de la reserva
        session_id: Session ID de Stripe (para la clave de cache)
    """
    try:
        print(f"🔄 Generando recomendación para reserva {reserva_id}, session {session_id[:40]}...")
        resultado = generate_packing_recommendation(reserva_id)
        
        # ✅ CORREGIDO: Guardar con session_id (lo que espera el endpoint)
        cache_key = f'recommendation_{session_id}'
        cache.set(cache_key, resultado, timeout=3600)
        print(f"✅ Recomendación guardada en cache con key: {cache_key[:60]}...")
        
    except Exception as e:
        print(f"❌ Error generando recomendación: {e}")
        # También guardar el error con session_id
        cache_key = f'recommendation_{session_id}'
        cache.set(cache_key, {"estado": "ERROR", "error": str(e)}, timeout=3600)

@api_view(['POST'])
def stripe_webhook(request):
    """
    Maneja los webhooks de Stripe, específicamente el evento checkout.session.completed
    para generar recomendaciones de viaje.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        
        # Verificar que es un checkout completado
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session.get('id')  # ✅ Obtener session_id de Stripe
            reserva_id = session.get('metadata', {}).get('reserva_id')
            
            print(f"📥 Webhook recibido: session_id={session_id[:40]}..., reserva_id={reserva_id}")
            
            if reserva_id and session_id:
                # ✅ CORREGIDO: Pasar AMBOS parámetros
                thread = Thread(
                    target=generate_and_cache_recommendation,
                    args=(int(reserva_id), session_id),
                    daemon=True
                )
                thread.start()
                print(f"✅ Thread de recomendación iniciado para session {session_id[:40]}...")
            else:
                print(f"⚠️ Webhook sin reserva_id o session_id: reserva={reserva_id}, session={session_id}")
            
        return Response({'status': 'success'})
        
    except stripe.error.SignatureVerificationError:
        return Response(
            {'error': 'Invalid signature'},
            status=400
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=400
        )
