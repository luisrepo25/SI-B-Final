# core/views.py
from datetime import timedelta, timezone
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect
import stripe
from django.conf import settings
from condominio.models import Paquete, Servicio, Suscripcion
from rest_framework.decorators import api_view
from rest_framework.response import Response
import os
from dotenv import load_dotenv
from rest_framework import status
from django.core.cache import cache
from .openai_client import get_openai_client  # ← cliente centralizado
from condominio.serializer import SuscripcionSerializer 
from threading import Thread
from .ai import generate_and_cache_recommendation

load_dotenv()
stripe.api_key = settings.STRIPE_SECRET_KEY
url_frontend = os.getenv("URL_FRONTEND", "http://127.0.0.1:3000")


# ============================================================================
# HELPER: Redirección a Deep Links sin validación de esquema
# ============================================================================
def redirect_to_deep_link(url):
    """
    Crea una respuesta de redirección HTTP 302 a cualquier URL, incluyendo
    esquemas personalizados como 'turismoapp://' sin validación.
    
    Solución para DisallowedRedirect: Django valida esquemas en HttpResponseRedirect.__init__()
    antes de que podamos establecer allowed_schemes. Esta función crea la response manualmente.
    """
    response = HttpResponse(status=302)
    response['Location'] = url
    return response


@api_view(["GET"])
def obtener_recomendacion(request):
    """Obtiene la recomendación generada para una sesión de pago específica."""
    session_id = request.query_params.get("session_id")  # ✅ Cambiado a 'session_id'
    
    if not session_id:
        return Response(
            {"error": "Se requiere el parámetro session_id"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Intentar obtener la recomendación del caché
    cache_key = f"recommendation_{session_id}"
    recommendation = cache.get(cache_key)
    if recommendation is None:
        return Response({"error": "No se encontró una recomendación para esta sesión"}, status=status.HTTP_404_NOT_FOUND)

    # Si la recomendación está en proceso, devolver 202 para indicar pending
    if isinstance(recommendation, dict) and recommendation.get("estado") == "GENERANDO":
        return Response({"status": "GENERANDO", "session_id": session_id}, status=status.HTTP_202_ACCEPTED)

    return Response({"recommendation": recommendation, "session_id": session_id})


# @permission_classes([IsAuthenticated])
@api_view(["POST"])
def crear_checkout_session(request):
    try:
        data = request.data
        nombre = data.get("nombre", "Reserva")
        precio = float(data.get("precio", 0))
        reserva_id = data.get("reserva_id")  # opcional, para enlazar con una reserva ya creada
        cantidad = int(data.get("cantidad", 1))

        if precio <= 0:
            return Response({"error": "Precio inválido"}, status=status.HTTP_400_BAD_REQUEST)

        # Construir URLs de retorno al FRONTEND (Netlify/Local)
        success_url_extra = f"&reserva_id={reserva_id}" if reserva_id else ""
        success_url = f"{url_frontend}/pago-exitoso?session_id={{CHECKOUT_SESSION_ID}}{success_url_extra}"
        cancel_url = f"{url_frontend}/pago-cancelado/"

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "bob",
                        "product_data": {"name": nombre},
                        "unit_amount": int(precio),  # se asume centavos enviados desde frontend
                    },
                    "quantity": cantidad,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "usuario_id": str(request.user.id) if request.user.is_authenticated else "anonimo",
                "recommendation_url": f"{request.build_absolute_uri('/api/recomendacion/')}?session_id={{CHECKOUT_SESSION_ID}}",
                "reserva_id": str(reserva_id) if reserva_id else None,
                "payment_type": "reserva_web" if reserva_id else "venta",
            },
        )

        return Response({"checkout_url": session.url})

    except Exception as e:
        print("❌ Error Stripe:", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  # ✅ DENTRO DEL except

# =====================================================
# CHECKOUT PARA RESERVA (WEB) – desde ID de reserva
# =====================================================
@api_view(["POST"])
def crear_checkout_reserva(request):
    """
    Crea una sesión de Checkout de Stripe a partir de una Reserva existente.
    Pensado para frontend web: devuelve la URL para redirigir al panel de pago.

    Body JSON esperado:
    { "reserva_id": 123 }

    Usa reserva.total y reserva.moneda (USD/BOB). Convierte a centavos.
    Agrega metadatos con usuario y reserva para facilitar verificación.
    """
    try:
        # Validar configuración
        if not settings.STRIPE_SECRET_KEY:
            return Response({
                "error": "Stripe no está configurado (STRIPE_SECRET_KEY ausente)"
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from decimal import Decimal
        from condominio.models import Reserva, Pago
        from datetime import date

        data = request.data or {}
        reserva_id = data.get("reserva_id") or request.query_params.get("reserva_id")
        if not reserva_id:
            return Response({"error": "Debe enviar 'reserva_id'"}, status=status.HTTP_400_BAD_REQUEST)

        # Buscar reserva
        try:
            reserva = Reserva.objects.get(id=reserva_id)
        except Reserva.DoesNotExist:
            return Response({"error": f"Reserva {reserva_id} no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        # Autorización básica: dueño o staff
        perfil = getattr(request.user, 'perfil', None)
        if request.user.is_authenticated and not request.user.is_staff:
            if not perfil or reserva.cliente_id != perfil.id:
                return Response({"error": "No tienes permiso para esta reserva"}, status=status.HTTP_403_FORBIDDEN)

        # Preparar monto en centavos
        try:
            amount_cents = int(Decimal(reserva.total) * 100)
        except Exception:
            return Response({"error": "Total inválido en la reserva"}, status=status.HTTP_400_BAD_REQUEST)

        if amount_cents <= 0:
            return Response({"error": "El total de la reserva debe ser mayor a 0"}, status=status.HTTP_400_BAD_REQUEST)

        # Moneda: mapear a valores aceptados por Stripe
        moneda = (reserva.moneda or 'BOB').upper()
        currency = 'usd' if moneda == 'USD' else 'bob'

        # URLs de retorno al FRONTEND (Netlify/Local) – se leen de URL_FRONTEND
        success_url = f"{url_frontend}/pago-exitoso?session_id={{CHECKOUT_SESSION_ID}}&reserva_id={reserva.id}"
        cancel_url = f"{url_frontend}/pago-cancelado?reserva_id={reserva.id}"

        # Construir sesión
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": f"Reserva #{reserva.id}",
                        "description": "Reserva múltiple de servicios"
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "payment_type": "reserva_web",
                "reserva_id": str(reserva.id),
                "usuario_id": str(request.user.id) if request.user.is_authenticated else "anonimo",
            },
            customer_email=(request.user.email if getattr(request.user, 'email', None) else None)
        )

        # Registrar/actualizar pago como pendiente con URL (opcional)
        try:
            Pago.objects.update_or_create(
                reserva=reserva,
                url_stripe=session.url,
                defaults={
                    'monto': Decimal(reserva.total),
                    'metodo': 'Tarjeta',
                    'estado': 'Pendiente',
                    'fecha_pago': date.today(),
                }
            )
        except Exception:
            # No hacer fallar el checkout por errores no críticos de persistencia
            pass

        return Response({
            "checkout_url": session.url,
            "session_id": session.id,
            "reserva_id": reserva.id,
            "moneda": moneda,
            "monto": float(reserva.total),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print("❌ Error Stripe (reserva web):", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def chatbot_turismo(request):
    pregunta = request.data.get("pregunta", "")
    if not pregunta:
        return Response({"error": "Debes enviar el campo 'pregunta'."}, status=400)

    paquetes = Paquete.objects.all().values(
        "nombre", "descripcion", "precio_base", "duracion"
    )
    servicios = Servicio.objects.all().values(
        "titulo", "descripcion", "precio_usd", "categoria__nombre"
    )

    contexto = "Paquetes turísticos:\n"
    for p in paquetes:
        contexto += f"- {p['nombre']} ({p['duracion']}) por ${p['precio_base']}: {p['descripcion']}\n"
    contexto += "\nServicios:\n"
    for s in servicios:
        contexto += f"- {s['titulo']} ({s['categoria__nombre']}): ${s['precio_usd']} — {s['descripcion']}\n"

    prompt = f"""
Eres un asesor turístico boliviano que trabaja en una agencia de viajes de Bolivia.
Tu tarea es recomendar paquetes y servicios turísticos basados en la información real que te proporcionaré.

Usa siempre el siguiente contexto para responder de forma amable, breve y precisa:
- Los datos incluyen paquetes turísticos, servicios, precios, duración, ubicación o ciudad, y descripciones.
- Si el usuario menciona lugares, ciudades o regiones (por ejemplo: "La Paz", "Uyuni", "Santa Cruz", "Cochabamba"), 
  busca entre los paquetes o servicios que coincidan con esa ubicación o tengan relación.
- Si el usuario pregunta por precios, muestra opciones económicas o menciona el precio en dólares.
- Si el usuario pide recomendaciones de aventura, cultura, gastronomía, o naturaleza, 
  filtra según la categoría o descripción más relacionada.

**Reglas obligatorias:**
1. Tus respuestas deben ser cortas, claras y sin adornos innecesarios.
2. Solo responde con información real de los paquetes o servicios que existen en el contexto.  
   Si no tienes la información, di literalmente: “No tengo información disponible sobre eso.”
3. Debes incluir **exactamente una URL válida** al final de tu respuesta.  
   - Si es un paquete, usa: {url_frontend}paquetes/{{id}}/
   - Si es un servicio, usa: {url_frontend}destinos/{{id}}/
   Ejemplo:  
   > Te recomiendo el paquete “Aventura Andina”, ideal para conocer el Salar de Uyuni. Cuesta 480 USD y dura 3 días.  
   > {url_frontend}paquetes/1/
4. **No inventes URLs ni IDs.** Usa solo los que estén en el contexto recibido.
5. No hables de otros países, únicamente de lugares dentro de Bolivia.
6. Si el usuario pide un lugar que no está en el contexto, responde:  
   > “No tengo información sobre ese destino en Bolivia.”

Recuerda: Responde como un asistente amable y profesional de turismo boliviano.

    {contexto}

    Usuario: {pregunta}
    Asistente:
    """

    try:
        client = get_openai_client()  # ← cliente centralizado

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Asistente turístico experto en Bolivia."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        respuesta = completion.choices[0].message.content
        return Response({"respuesta": respuesta})
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def crear_checkout_session_suscripcion(request):
    try:
        data = request.data

        # Datos enviados desde el frontend

        usuario_id = data.get("usuario_id")
        plan_id = data.get("plan_id")
        nombre_empresa = data.get("nombre_empresa", "Proveedor sin nombre")
        descripcion = data.get("descripcion", "")
        telefono = data.get("telefono", "")
        sitio_web = data.get("sitio_web", "")

        # Validaciones básicas
        if not plan_id:
            return Response({"error": "Falta plan_id"}, status=status.HTTP_400_BAD_REQUEST)
        if not usuario_id:
            return Response({"error": "Falta usuario_id"}, status=status.HTTP_400_BAD_REQUEST)

        from condominio.models import Usuario, Proveedor, Suscripcion, Plan
        from django.utils import timezone
        from datetime import timedelta
        from django.contrib.auth.models import Group

        try:
            usuario = Usuario.objects.get(id=usuario_id)
            plan = Plan.objects.get(id=plan_id)
            print(f"✅ Usuario: {usuario.id} - {usuario.nombre} - Rol actual ID: {usuario.rol_id}")
        except Usuario.DoesNotExist:
            return Response({"error": f"Usuario con ID={usuario_id} no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        except Plan.DoesNotExist:
            return Response({"error": "Plan no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        if not plan.activo:
            return Response({"error": "El plan seleccionado no está disponible"}, status=status.HTTP_400_BAD_REQUEST)

        print("🔄 Cambiando rol del usuario a rol_id=3...")
        from condominio.models import Rol
        try:
            rol_proveedor = Rol.objects.get(id=3)
            usuario.rol = rol_proveedor
            usuario.save()
            print(f"✅ Rol cambiado: usuario {usuario.id} ahora tiene rol_id={usuario.rol.id}")
        except Rol.DoesNotExist:
            print("❌ Error: No existe el rol con id=3")

        grupo_proveedor, creado_grupo = Group.objects.get_or_create(name='proveedor')
        usuario.user.groups.clear()
        usuario.user.groups.add(grupo_proveedor)
        print(f"✅ Grupo Django actualizado: usuario agregado a grupo 'proveedor'")

        print(f"🔍 Creando/actualizando proveedor para usuario {usuario.id}...")
        proveedor, creado_proveedor = Proveedor.objects.get_or_create(
            usuario=usuario,
            defaults={
                "nombre_empresa": nombre_empresa,
                "descripcion": descripcion,
                "telefono": telefono,
                "sitio_web": sitio_web,
            },
        )

        if not creado_proveedor:
            update_fields = {}
            if nombre_empresa and nombre_empresa != "Proveedor sin nombre":
                update_fields["nombre_empresa"] = nombre_empresa
            if descripcion:
                update_fields["descripcion"] = descripcion
            if telefono:
                update_fields["telefono"] = telefono
            if sitio_web:
                update_fields["sitio_web"] = sitio_web
            if update_fields:
                print(f"🔄 Actualizando proveedor con: {update_fields}")
                Proveedor.objects.filter(id=proveedor.id).update(**update_fields)
                proveedor.refresh_from_db()

        fecha_inicio = timezone.now().date()
        duracion_dias = {
            "mensual": 30,
            "trimestral": 90,
            "semestral": 180,
            "anual": 365
        }
        dias_duracion = duracion_dias.get(plan.duracion.lower(), 30)
        fecha_fin = fecha_inicio + timedelta(days=dias_duracion)
        print(f"📅 Suscripción: {fecha_inicio} a {fecha_fin} ({dias_duracion} días)")

        precio_centavos = int(float(plan.precio) * 100)
        print(f"💰 Stripe amount: {precio_centavos} centavos")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "bob",
                        "product_data": {
                            "name": plan.nombre,
                            "description": plan.descripcion
                        },
                        "unit_amount": precio_centavos,
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{url_frontend}",
            cancel_url=f"{url_frontend}/pago-cancelado/",
            metadata={
                "usuario_id": str(usuario.id),
                "proveedor_id": str(proveedor.id),
                "plan_id": str(plan.id),
                "payment_type": "suscripcion",
                "plan_nombre": plan.nombre,
                "precio_total": str(plan.precio),
                "nuevo_rol_id": "3",
            },
        )

        print(f"✅ Sesión Stripe creada: {session.id}")

        suscripcion = Suscripcion.objects.create(
            proveedor=proveedor,
            plan=plan,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activa=True,
            stripe_session_id=session.id,
        )

        print(f"✅ SUSCRIPCIÓN CREADA - ID: {suscripcion.id}")
        print(f"   Proveedor: {suscripcion.proveedor.nombre_empresa}")
        print(f"   Plan: {suscripcion.plan.nombre}")
        print(f"   Activa: {suscripcion.activa}")

        try:
            from .recommendation_utils import generar_recomendacion_equipaje
            recomendacion = generar_recomendacion_equipaje(plan.nombre, str(usuario.id))
            cache_key = f"recommendation_{session.id}"
            cache.set(cache_key, recomendacion, timeout=3600)
            print(f"💾 Recomendación guardada en cache: {cache_key}")
        except ImportError:
            print("⚠️  No se pudo importar recommendation_utils, omitiendo recomendación")
        except Exception as e:
            print(f"⚠️  Error generando recomendación: {e}")

        return Response({
            "checkout_url": session.url,
            "session_id": session.id,
            "suscripcion_id": suscripcion.id,
            "proveedor_id": proveedor.id,
            "plan_nombre": plan.nombre,
            "precio": str(plan.precio),
            "duracion": plan.duracion,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "usuario_actualizado": {
                "id": usuario.id,
                "nombre": usuario.nombre,
                "nuevo_rol_id": 3,
                "rol_anterior": usuario.rol_id,
                "nombre_empresa": proveedor.nombre_empresa
            },
            "mensaje": f"Suscripción creada exitosamente. El usuario ID={usuario.id} ahora tiene rol_id=3."
        })

    except Exception as e:
        print("❌ Error en crear_checkout_session_suscripcion:", e)
        import traceback
        print("📝 Traceback:", traceback.format_exc())
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def verificar_pago(request):
    session_id = request.GET.get("session_id")

    if not session_id:
        return Response({"error": "Falta session_id"}, status=400)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        pago_exitoso = session.payment_status == "paid"

        # extraer metadata
        metadata = getattr(session, "metadata", {}) or {}
        payment_type = metadata.get("payment_type", "venta")

        # ✅ CORREGIDO: Solo verificar pago, sin crear suscripción duplicada
        # La suscripción ya se crea en crear_checkout_session_suscripcion
        # Si el pago fue exitoso, iniciar generación de recomendación (si aplica)
        recommendation_status = None
        reserva_id = metadata.get('reserva_id')
        if pago_exitoso and reserva_id:
            try:
                cache_key = f"recommendation_{session_id}"
                if not cache.get(cache_key):
                    cache.set(cache_key, {"estado": "GENERANDO"}, timeout=3600)
                    thread = Thread(
                        target=generate_and_cache_recommendation,
                        args=(int(reserva_id), session_id),
                        daemon=True,
                    )
                    thread.start()
                recommendation_status = cache.get(cache_key)
            except Exception as e:
                print(f"Error iniciando generación de recomendación en verificar_pago: {e}")

        return Response({
            "pago_exitoso": pago_exitoso,
            "cliente_email": session.customer_details.email if session.customer_details else None,
            "monto_total": session.amount_total,
            "moneda": session.currency,
            "payment_type": payment_type,
            "recommendation_status": recommendation_status,
        })

    except Exception as e:
        print("❌ Error verificando sesión:", e)
        return Response({"error": str(e)}, status=500)
    

# ============================================================================
# 📱 ENDPOINTS ESPECÍFICOS PARA APP MÓVIL FLUTTER - STRIPE CON DEEP LINKS
# ============================================================================

@api_view(["POST"])
def crear_checkout_session_mobile(request):
    """
    Crea una sesión de Stripe Checkout específica para app móvil.
    Maneja deep links para retornar automáticamente a la app después del pago.
    
    POST /api/crear-checkout-session-mobile/
    
    Headers:
        Authorization: Token <user_token>
        Content-Type: application/json
    
    Body:
    {
      "reserva_id": 35,
      "nombre": "Tour Salar de Uyuni",
      "precio": 48000,        // EN CENTAVOS (480.00 BOB = 48000)
      "cantidad": 1,          // opcional, default=1
      "moneda": "BOB",        // opcional, default=BOB
      "cliente_email": "user@email.com"  // opcional
    }
    
    Response:
    {
      "success": true,
      "checkout_url": "https://checkout.stripe.com/...",
      "session_id": "cs_test_...",
      "reserva_id": 35,
      "monto": 480.00,
      "moneda": "BOB"
    }
    """
    from condominio.models import Reserva
    from decimal import Decimal
    
    try:
        # Validar autenticación
        if not request.user.is_authenticated:
            return Response({
                "success": False,
                "error": "Debes estar autenticado para crear una sesión de pago"
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Extraer datos del request
        data = request.data
        reserva_id = data.get("reserva_id")
        nombre = data.get("nombre", "Reserva")
        precio = data.get("precio")
        cantidad = int(data.get("cantidad", 1))
        moneda = data.get("moneda", "BOB").upper()
        cliente_email = data.get("cliente_email", None)
        
        # Validaciones de campos obligatorios
        if not reserva_id:
            return Response({
                "success": False,
                "error": "Campo 'reserva_id' es obligatorio",
                "campo_faltante": "reserva_id",
                "ejemplo": {
                    "reserva_id": 35,
                    "nombre": "Tour Uyuni",
                    "precio": 48000
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not precio:
            return Response({
                "success": False,
                "error": "Campo 'precio' es obligatorio (en centavos)",
                "campo_faltante": "precio",
                "ejemplo": "Para 480 BOB, enviar: 48000"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convertir precio a int y validar
        try:
            precio = int(precio)
        except (ValueError, TypeError):
            return Response({
                "success": False,
                "error": "El precio debe ser un número entero en centavos"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if precio <= 0:
            return Response({
                "success": False,
                "error": "El precio debe ser mayor a 0 (en centavos)",
                "ejemplo": "Para 480 BOB, enviar: 48000"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que la reserva existe
        try:
            reserva = Reserva.objects.get(id=reserva_id)
        except Reserva.DoesNotExist:
            return Response({
                "success": False,
                "error": f"Reserva con ID {reserva_id} no encontrada"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar que el usuario tiene permiso para esta reserva
        perfil = getattr(request.user, 'perfil', None)
        if not request.user.is_staff:  # Los admins pueden pagar cualquier reserva
            if not perfil or reserva.cliente.id != perfil.id:
                return Response({
                    "success": False,
                    "error": "No tienes permiso para acceder a esta reserva"
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Configurar URLs de callback del backend (NO del frontend)
        base_url = "https://backendspring2-production.up.railway.app/api"
        success_url = f"{base_url}/pago-exitoso-mobile/?session_id={{CHECKOUT_SESSION_ID}}&reserva_id={reserva_id}"
        cancel_url = f"{base_url}/pago-cancelado-mobile/?reserva_id={reserva_id}"
        
        # Preparar metadata para Stripe
        metadata = {
            "usuario_id": str(request.user.id),
            "reserva_id": str(reserva_id),
            "payment_type": "reserva",
            "platform": "mobile_flutter",
            "titulo": nombre,
            "cliente_perfil_id": str(perfil.id) if perfil else None,
            "cliente_email": request.user.email
        }
        
        # Preparar parámetros de sesión Stripe
        session_params = {
            "payment_method_types": ["card"],
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": moneda.lower(),
                    "product_data": {
                        "name": nombre,
                        "description": f"Reserva #{reserva_id}"
                    },
                    "unit_amount": precio,  # Ya en centavos
                },
                "quantity": cantidad,
            }],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata
        }
        
        # Agregar email si se proporciona
        if cliente_email:
            session_params["customer_email"] = cliente_email
        elif request.user.email:
            session_params["customer_email"] = request.user.email
        
        # Crear sesión en Stripe
        session = stripe.checkout.Session.create(**session_params)
        
        # Log para debugging
        print(f"✅ Sesión Stripe móvil creada")
        print(f"   Session ID: {session.id}")
        print(f"   Reserva ID: {reserva_id}")
        print(f"   Usuario: {request.user.email}")
        print(f"   Monto: {precio/100} {moneda}")
        print(f"   Success URL: {success_url}")
        
        # Devolver respuesta exitosa
        return Response({
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id,
            "reserva_id": reserva_id,
            "monto": precio / 100,  # Convertir a formato decimal para mostrar
            "moneda": moneda,
            "expires_at": session.expires_at
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error creando checkout móvil: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response({
            "success": False,
            "error": "Error al crear sesión de pago",
            "detalle": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def pago_exitoso_mobile(request):
    """
    Callback de Stripe después de pago exitoso.
    Valida el pago, actualiza la reserva y redirige a la app móvil con deep link.
    
    GET /api/pago-exitoso-mobile/?session_id=cs_test_...&reserva_id=35
    
    Este endpoint:
    1. Recibe callback de Stripe con session_id
    2. Verifica el pago con Stripe API
    3. Actualiza el estado de la reserva en la base de datos
    4. Crea registro de pago
    5. Redirige a deep link: turismoapp://payment-success?...
    
    VERSIÓN: 2024-11-03 v2 - Fix allowed_schemes per-response
    """
    from condominio.models import Reserva, Pago
    from datetime import date
    from decimal import Decimal
    
    session_id = request.GET.get("session_id")
    reserva_id = request.GET.get("reserva_id")
    
    print(f"\n{'='*60}")
    print(f"📱 CALLBACK PAGO EXITOSO MÓVIL [v2-fixed-allowed-schemes]")
    print(f"{'='*60}")
    print(f"   Session ID: {session_id}")
    print(f"   Reserva ID: {reserva_id}")
    
    # Validar parámetros
    if not session_id or not reserva_id:
        print(f"❌ Error: Faltan parámetros")
        missing_params_link = "turismoapp://payment-error?error=missing_params"
        return redirect_to_deep_link(missing_params_link)
    
    try:
        # Verificar sesión con Stripe API
        session = stripe.checkout.Session.retrieve(session_id)
        
        print(f"   Estado de pago: {session.payment_status}")
        print(f"   Monto: {session.amount_total} centavos")
        print(f"   Moneda: {session.currency}")
        
        # Validar que el pago fue completado
        if session.payment_status == "paid":
            # Buscar la reserva
            try:
                reserva = Reserva.objects.get(id=reserva_id)
                
                # Actualizar estado de la reserva
                estado_anterior = reserva.estado
                reserva.estado = "PAGADA"
                reserva.save(update_fields=['estado'])
                
                print(f"   ✅ Reserva actualizada: {estado_anterior} → PAGADA")
                
                # Calcular monto en formato decimal
                monto_decimal = Decimal(str(session.amount_total / 100))
                
                # Crear o actualizar registro de pago (prevenir duplicados)
                pago, created = Pago.objects.get_or_create(
                    reserva=reserva,
                    url_stripe=session.url,
                    defaults={
                        'monto': monto_decimal,
                        'metodo': 'Tarjeta',
                        'estado': 'Confirmado',
                        'fecha_pago': date.today()
                    }
                )
                
                if created:
                    print(f"   ✅ Pago registrado: ID {pago.id}, Monto {monto_decimal}")
                else:
                    print(f"   ℹ️  Pago ya existía: ID {pago.id} (prevención de duplicados)")
                
                # Iniciar generación de recomendación en background (sin webhooks)
                try:
                    cache_key = f"recommendation_{session_id}"
                    # Evitar lanzar múltiples procesos si ya existe un marcador
                    if not cache.get(cache_key):
                        cache.set(cache_key, {"estado": "GENERANDO"}, timeout=3600)
                        thread = Thread(
                            target=generate_and_cache_recommendation,
                            args=(int(reserva_id), session_id),
                            daemon=True,
                        )
                        thread.start()
                        print(f"   Recomendación: generación en background iniciada para session {session_id}")
                except Exception as e:
                    print(f"   Error iniciando generación de recomendación: {e}")

                # Construir deep link de éxito
                deep_link = (
                    f"turismoapp://payment-success"
                    f"?session_id={session_id}"
                    f"&reserva_id={reserva_id}"
                    f"&monto={monto_decimal}"
                    f"&status=completed"
                    f"&moneda={session.currency.upper()}"
                )
                
                print(f"   🚀 Redirigiendo a app: {deep_link[:80]}...")
                print(f"{'='*60}\n")
                
                # Redirigir a la app móvil usando deep link personalizado
                return redirect_to_deep_link(deep_link)
                
            except Reserva.DoesNotExist:
                print(f"   ❌ Error: Reserva {reserva_id} no encontrada")
                error_link = (
                    f"turismoapp://payment-error"
                    f"?error=reserva_not_found"
                    f"&reserva_id={reserva_id}"
                )
                return redirect_to_deep_link(error_link)
        
        elif session.payment_status == "unpaid":
            # Pago no completado
            print(f"   ⚠️  Pago no completado: {session.payment_status}")
            pending_link = (
                f"turismoapp://payment-pending"
                f"?session_id={session_id}"
                f"&reserva_id={reserva_id}"
                f"&status={session.payment_status}"
            )
            return redirect_to_deep_link(pending_link)
        
        else:
            # Otro estado
            print(f"   ⚠️  Estado inesperado: {session.payment_status}")
            error_status_link = (
                f"turismoapp://payment-error"
                f"?error=unexpected_status"
                f"&status={session.payment_status}"
                f"&reserva_id={reserva_id}"
            )
            return redirect_to_deep_link(error_status_link)
    
    except Exception as e:
        print(f"   ❌ Error procesando pago: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        exception_link = (
            f"turismoapp://payment-error"
            f"?error=processing_error"
            f"&session_id={session_id}"
        )
        return redirect_to_deep_link(exception_link)


@api_view(["GET"])
def pago_cancelado_mobile(request):
    """
    Callback cuando el usuario cancela el pago en Stripe.
    Redirige a la app móvil con deep link de cancelación.
    
    GET /api/pago-cancelado-mobile/?reserva_id=35
    """
    from condominio.models import Reserva
    
    reserva_id = request.GET.get("reserva_id")
    
    print(f"\n{'='*60}")
    print(f"❌ CALLBACK PAGO CANCELADO MÓVIL")
    print(f"{'='*60}")
    print(f"   Reserva ID: {reserva_id}")
    
    try:
        if reserva_id:
            # Opcionalmente actualizar estado de reserva
            try:
                reserva = Reserva.objects.get(id=reserva_id)
                # Mantener en PENDIENTE para que pueda reintentar
                if reserva.estado not in ['PAGADA', 'CONFIRMADA', 'COMPLETADA']:
                    reserva.estado = 'PENDIENTE'
                    reserva.save(update_fields=['estado'])
                    print(f"   ℹ️  Reserva mantenida en PENDIENTE para reintento")
            except Reserva.DoesNotExist:
                print(f"   ⚠️  Reserva {reserva_id} no encontrada")
        
        # Construir deep link de cancelación
        deep_link = f"turismoapp://payment-cancel?reserva_id={reserva_id}&status=cancelled"
        
        print(f"   🚀 Redirigiendo a app: {deep_link}")
        print(f"{'='*60}\n")
        
        return redirect_to_deep_link(deep_link)
    
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        print(f"{'='*60}\n")
        
        cancel_link = f"turismoapp://payment-cancel?status=cancelled"
        return redirect_to_deep_link(cancel_link)


@api_view(["GET"])
def listar_suscripciones(request):
    from condominio.models import Suscripcion

    usuario_id = request.GET.get("usuario_id")
    proveedor_id = request.GET.get("proveedor_id")
    activas = request.GET.get("activas")  # "true" / "false"

    suscripciones = Suscripcion.objects.all()

    # Filtros opcionales
    if usuario_id:
        suscripciones = suscripciones.filter(proveedor__usuario_id=usuario_id)

    if proveedor_id:
        suscripciones = suscripciones.filter(proveedor_id=proveedor_id)

    if activas is not None:
        if activas.lower() == "true":
            suscripciones = suscripciones.filter(activa=True)
        elif activas.lower() == "false":
            suscripciones = suscripciones.filter(activa=False)

    serializer = SuscripcionSerializer(suscripciones, many=True)
    return Response(serializer.data)
