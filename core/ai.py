# core/ai.py
import os
import json
from core.openai_client import get_openai_client  # ← ¡ya no importamos desde core.views!
from condominio.models import Reserva, Paquete, Servicio

def generate_packing_recommendation(reserva_id: int) -> dict:
    """
    Genera recomendaciones de qué llevar para un viaje basado en la reserva.
    Similar al chatbot turístico pero especializado en recomendaciones de equipaje.
    """
    try:
        # Cargar datos de la reserva y sus relaciones
        reserva = Reserva.objects.select_related('cliente', 'paquete', 'servicio').get(id=reserva_id)
        
        # ✅ VALIDACIÓN: Verificar que la reserva tenga paquete o servicio
        if not reserva.paquete and not reserva.servicio:
            print(f"⚠️ Reserva #{reserva_id} sin paquete ni servicio, generando recomendación genérica")
            return {
                "estado": "OK",
                "recomendacion": {
                    "texto": "¡Prepárate para tu viaje! Aquí tienes recomendaciones generales para tu aventura en Bolivia.",
                    "items": [
                        {
                            "categoria": "Ropa",
                            "items": [
                                "Ropa cómoda y versátil",
                                "Chaqueta ligera o cortavientos",
                                "Calzado cómodo para caminar",
                                "Gorro y protección solar"
                            ],
                            "prioridad": "alta"
                        },
                        {
                            "categoria": "Documentos",
                            "items": [
                                "Documento de identidad o pasaporte",
                                "Confirmación de reserva",
                                "Seguro de viaje (recomendado)"
                            ],
                            "prioridad": "alta"
                        },
                        {
                            "categoria": "Equipo",
                            "items": [
                                "Cámara o teléfono con cámara",
                                "Cargador y batería extra",
                                "Mochila pequeña"
                            ],
                            "prioridad": "media"
                        },
                        {
                            "categoria": "Otros",
                            "items": [
                                "Agua y snacks",
                                "Protector solar y repelente",
                                "Dinero en efectivo",
                                "Medicamentos personales"
                            ],
                            "prioridad": "media"
                        }
                    ]
                }
            }
        
        # Determinar si es paquete o servicio y obtener datos
        if reserva.paquete:
            item = reserva.paquete
            nombre = item.nombre
            descripcion = item.descripcion
            duracion = item.duracion
            incluye = item.incluye if hasattr(item, 'incluye') else []
            no_incluye = item.no_incluye if hasattr(item, 'no_incluye') else []
        else:
            item = reserva.servicio
            nombre = item.titulo
            descripcion = item.descripcion
            duracion = item.duracion
            incluye = item.servicios_incluidos if hasattr(item, 'servicios_incluidos') else []
            no_incluye = []

        prompt = f"""
Eres un experto guía de viajes boliviano. Tu tarea es generar una lista detallada y personalizada de qué debe llevar el viajero para este viaje específico.

INFORMACIÓN DEL VIAJE:
- Destino/Experiencia: {nombre}
- Duración: {duracion}
- Descripción: {descripcion}
- Servicios incluidos: {', '.join(incluye) if isinstance(incluye, list) else incluye}
- No incluido: {', '.join(no_incluye) if isinstance(no_incluye, list) else no_incluye}

Genera un JSON con el siguiente formato exacto (no incluyas explicaciones fuera del JSON):
{{
    "texto": "Un mensaje amigable y personalizado de 2-3 líneas explicando las recomendaciones principales",
    "items": [
        {{
            "categoria": "Ropa",
            "items": ["item1", "item2", "item3"],
            "prioridad": "alta/media/baja"
        }},
        {{
            "categoria": "Documentos",
            "items": ["item1", "item2"],
            "prioridad": "alta"
        }},
        {{
            "categoria": "Equipo",
            "items": ["item1", "item2"],
            "prioridad": "media"
        }},
        {{
            "categoria": "Otros",
            "items": ["item1", "item2"],
            "prioridad": "baja"
        }}
    ]
}}

Asegúrate de:
1. Adaptar los items según el tipo de viaje y duración
2. Considerar el clima y geografía del destino
3. Mencionar elementos de seguridad según la actividad
4. Incluir documentos necesarios
5. Sugerir equipo específico si el viaje lo requiere
"""

        client = get_openai_client()  # ← cliente centralizado
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "Experto en planificación de viajes por Bolivia.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        # Intentar parsear la respuesta como JSON
        try:
            recomendacion = json.loads(completion.choices[0].message.content)
            return {
                "estado": "OK",
                "recomendacion": recomendacion
            }
        except json.JSONDecodeError:
            # Si no es JSON válido, devolver el texto como está
            return {
                "estado": "ERROR",
                "error": "Formato inválido en la respuesta",
                "texto_original": completion.choices[0].message.content
            }
            
    except Reserva.DoesNotExist:
        return {
            "estado": "ERROR",
            "error": f"No se encontró la reserva con ID {reserva_id}"
        }
    except Exception as e:
        return {
            "estado": "ERROR",
            "error": str(e)
        }
