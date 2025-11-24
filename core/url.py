# core/url.py
from django.urls import path
from .views import (
    chatbot_turismo,
    crear_checkout_session,
    crear_checkout_reserva,
    crear_checkout_session_suscripcion,
    obtener_recomendacion,
    verificar_pago,
    # Nuevos endpoints para app móvil con deep links
    crear_checkout_session_mobile,
    pago_exitoso_mobile,
    pago_cancelado_mobile,
)
from .webhooks import stripe_webhook

urlpatterns = [
    # Endpoints web existentes
    path('crear-checkout-session/', crear_checkout_session, name='crear-checkout-session'),
    path('crear-checkout-reserva/', crear_checkout_reserva, name='crear-checkout-reserva'),
    path('crear-checkout-session-suscripcion/', crear_checkout_session_suscripcion, name='crear-checkout-session-suscripcion'),
    path('chatbot/turismo/', chatbot_turismo, name='chatbot-turismo'),
    path('recomendacion/', obtener_recomendacion, name='obtener-recomendacion'),
    path('verificar-pago/', verificar_pago, name='verificar-pago'),
    path('webhook/stripe/', stripe_webhook, name='stripe-webhook'),
    # Nuevos endpoints para app móvil Flutter con deep links
    path('crear-checkout-session-mobile/', crear_checkout_session_mobile, name='crear-checkout-mobile'),
    path('pago-exitoso-mobile/', pago_exitoso_mobile, name='pago-exitoso-mobile'),
    path('pago-cancelado-mobile/', pago_cancelado_mobile, name='pago-cancelado-mobile'),


]
