from rest_framework import serializers
from authz.serializer import RolSerializer
from django.contrib.auth.models import User
from .models import (
    Categoria,
    Proveedor,
    Servicio,
    Suscripcion,
    Usuario,
    Campania,
    Paquete,
    PaqueteServicio,
    Cupon,
    Reserva,
    Visitante,
    ReservaVisitante,
    CampaniaServicio,
    Pago,
    ReglaReprogramacion,
    HistorialReprogramacion,
    ConfiguracionGlobalReprogramacion,
    Reprogramacion,
    ComprobantePago,
    ReservaServicio,
    FCMDevice,
    CampanaNotificacion,
    Plan
    # Proveedor, Suscripcion - MODELOS REMOVIDOS POR MIGRACION 0009
)
# =====================================================
# 🔗 RESERVA_SERVICIO
# =====================================================
class ReservaServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservaServicio
        fields = ['servicio', 'fecha']

# =====================================================
# Reserva con servicios múltiples
# =====================================================
class ReservaConServiciosSerializer(serializers.ModelSerializer):
    # Entrada: aceptar lista "servicios" como write_only
    servicios = ReservaServicioSerializer(many=True, write_only=True)
    # Salida: devolver los servicios creados usando el related_name del modelo
    servicios_reservados = ReservaServicioSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = Reserva
        fields = ['id', 'fecha', 'estado', 'total', 'moneda', 'cliente', 'servicios', 'servicios_reservados']

    def create(self, validated_data):
        servicios_data = validated_data.pop('servicios', [])
        reserva = Reserva.objects.create(**validated_data)
        for servicio_data in servicios_data:
            ReservaServicio.objects.create(reserva=reserva, **servicio_data)

        # Si hay 2 o más servicios, convertirlo en un Paquete personalizado
        try:
            if len(servicios_data) >= 2:
                from decimal import Decimal

                paquete = Paquete.objects.create(
                    nombre=f"Paquete Personalizado #{reserva.id}",
                    es_personalizado=True,
                    descripcion="Paquete personalizado generado a partir de múltiples servicios seleccionados por el usuario.",
                    duracion=f"{len(servicios_data)} actividades",
                    precio_base=Decimal(str(reserva.total)),
                    precio_bob=Decimal(str(reserva.total)) if str(reserva.moneda).upper() == 'BOB' else None,
                    # Defaults del modelo cubren cupos y estado
                    fecha_inicio=reserva.fecha,
                    fecha_fin=reserva.fecha,
                    punto_salida="A definir",
                )

                # Asociar los servicios seleccionados al paquete (itinerario simple)
                for idx, sdata in enumerate(servicios_data, start=1):
                    try:
                        PaqueteServicio.objects.create(
                            paquete=paquete,
                            # sdata['servicio'] ya es una instancia de Servicio validada por DRF
                            servicio=sdata.get('servicio'),
                            dia=idx,
                            orden=1,
                        )
                    except Exception:
                        # No bloquear por un servicio individual
                        pass

                # Vincular la reserva con el paquete personalizado
                reserva.paquete = paquete
                reserva.save(update_fields=['paquete'])
        except Exception:
            # No bloquear la creación de la reserva si falla la generación del paquete
            pass

        return reserva


class ReservaSalidaSerializer(serializers.ModelSerializer):
    """Serializer de salida para evitar intentar leer el campo de entrada 'servicios'.
    Expone los servicios creados a través del related_name 'servicios_reservados'.
    """
    servicios_reservados = ReservaServicioSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = Reserva
        # Incluir 'paquete' para que el frontend pueda redirigir al detalle si se generó un paquete personalizado
        fields = ['id', 'fecha', 'estado', 'total', 'moneda', 'cliente', 'paquete', 'servicios_reservados']


# =====================================================
# 🏷️ CATEGORIA
# =====================================================
class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 🧍 USUARIO
# =====================================================
class UsuarioSerializer(serializers.ModelSerializer):
    # anidar el rol como objeto para que sea consistente con el login
    rol = RolSerializer(read_only=True)

    class Meta:
        model = Usuario
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 👤 PERFIL DE USUARIO (Para clientes)
# =====================================================
class PerfilUsuarioSerializer(serializers.ModelSerializer):
    """Serializer completo para el perfil de usuario con información personal"""

    rol = RolSerializer(read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    fecha_registro = serializers.DateTimeField(
        source="user.date_joined", read_only=True
    )
    ultimo_acceso = serializers.DateTimeField(source="user.last_login", read_only=True)

    # Estadísticas del usuario
    total_reservas = serializers.SerializerMethodField()
    reservas_activas = serializers.SerializerMethodField()
    total_gastado = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "nombre",
            "rubro",
            "num_viajes",
            "rol",
            "telefono",
            "fecha_nacimiento",
            "genero",
            "documento_identidad",
            "pais",
            "email",
            "username",
            "fecha_registro",
            "ultimo_acceso",
            "total_reservas",
            "reservas_activas",
            "total_gastado",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_reservas(self, obj):
        """Total de reservas del usuario"""
        return obj.reservas.count()

    def get_reservas_activas(self, obj):
        """Reservas que no están canceladas o completadas"""
        return obj.reservas.exclude(estado__in=["CANCELADA", "COMPLETADA"]).count()

    def get_total_gastado(self, obj):
        """Total gastado en reservas pagadas"""
        from django.db.models import Sum

        total = obj.reservas.filter(estado="PAGADA").aggregate(total=Sum("total"))[
            "total"
        ]
        return float(total or 0)


# =====================================================
# 🎫 SOPORTE - PANEL SERIALIZERS
# =====================================================
class SoporteResumenSerializer(serializers.ModelSerializer):
    """Serializer para mostrar resumen de tickets de soporte del usuario"""

    tickets_total = serializers.SerializerMethodField()
    proveedor_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Paquete
        fields = [
            "id",
            "nombre",
            "descripcion",
            "duracion",
            "precio_base",
            "precio_bob",
            "cupos_disponibles",
            "cupos_ocupados",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "destacado",
            "imagen_principal",
            "punto_salida",
            "incluye",
            "no_incluye",
            "servicios_incluidos",
            "itinerario",
            "precios",
            "disponibilidad",
            "campania_info",
            "created_at",
            "es_personalizado",
            "proveedor",
            "proveedor_info",
        ]
        read_only_fields = ["id", "created_at", "es_personalizado"]

    def get_proveedor_info(self, obj):
        if obj.proveedor:
            return {
                "id": obj.proveedor.id,
                "nombre": obj.proveedor.nombre,
                "telefono": obj.proveedor.telefono,
                "email": getattr(obj.proveedor, "user", None) and getattr(obj.proveedor.user, "email", None),
                "rubro": obj.proveedor.rubro,
                "rol": getattr(obj.proveedor.rol, "nombre", None),
            }
        return None
        model = Campania
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        fecha_inicio = attrs.get(
            "fecha_inicio", getattr(self.instance, "fecha_inicio", None)
        )
        fecha_fin = attrs.get("fecha_fin", getattr(self.instance, "fecha_fin", None))
        monto = attrs.get("monto", getattr(self.instance, "monto", None))

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise serializers.ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )
        if monto is not None and monto <= 0:
            raise serializers.ValidationError(
                "El monto de descuento debe ser mayor que cero."
            )
        return attrs


# =====================================================
# 📦 PAQUETE COMPLETO (Campaña + Servicios)
# =====================================================
class PaqueteCompletoSerializer(serializers.ModelSerializer):
    """Serializer para mostrar paquetes completos con servicios incluidos"""

    servicios_incluidos = serializers.SerializerMethodField()
    cupones_disponibles = serializers.SerializerMethodField()
    precio_total_servicios = serializers.SerializerMethodField()

    class Meta:
        model = Campania
        fields = "__all__"
        read_only_fields = ["id", "created_at"]

    def get_servicios_incluidos(self, obj):
        """Obtiene todos los servicios incluidos en esta campaña/paquete"""
        from .models import CampaniaServicio

        campania_servicios = CampaniaServicio.objects.filter(
            campania=obj
        ).select_related("servicio__categoria")
        return [
            {
                "id": cs.servicio.pk,
                "titulo": cs.servicio.titulo,
                "descripcion": cs.servicio.descripcion,
                "duracion": cs.servicio.duracion,
                "capacidad_max": cs.servicio.capacidad_max,
                "punto_encuentro": cs.servicio.punto_encuentro,
                "precio_usd": float(cs.servicio.precio_usd),
                "categoria": (
                    cs.servicio.categoria.nombre if cs.servicio.categoria else None
                ),
                "imagen_url": cs.servicio.imagen_url,
                "estado": cs.servicio.estado,
                "servicios_incluidos": cs.servicio.servicios_incluidos,
            }
            for cs in campania_servicios
        ]

    def get_cupones_disponibles(self, obj):
        """Obtiene cupones disponibles para esta campaña"""
        from django.db import models

        cupones = obj.cupones.filter(nro_usos__lt=models.F("cantidad_max"))
        return [
            {
                "id": cupon.pk,
                "usos_restantes": cupon.cantidad_max - cupon.nro_usos,
                "cantidad_max": cupon.cantidad_max,
                "nro_usos": cupon.nro_usos,
            }
            for cupon in cupones
        ]

    def get_precio_total_servicios(self, obj):
        """Calcula precio total de servicios incluidos en USD"""
        from .models import CampaniaServicio

        campania_servicios = CampaniaServicio.objects.filter(
            campania=obj
        ).select_related("servicio")
        total_usd = sum(cs.servicio.precio_usd for cs in campania_servicios)
        return {
            "total_usd": float(total_usd),
            "cantidad_servicios": len(campania_servicios),
        }


# =====================================================
# 📦 PAQUETE TURÍSTICO (Nuevo modelo)
# =====================================================
class PaqueteServicioSerializer(serializers.ModelSerializer):
    """Serializer para la relación Paquete-Servicio con información del itinerario"""

    servicio = serializers.SerializerMethodField()
    punto_encuentro_final = serializers.SerializerMethodField()

    class Meta:
        model = PaqueteServicio
        fields = [
            "dia",
            "orden",
            "hora_inicio",
            "hora_fin",
            "notas",
            "punto_encuentro_override",
            "punto_encuentro_final",
            "servicio",
        ]

    def get_servicio(self, obj):
        """Información del servicio incluido"""
        return {
            "id": obj.servicio.pk,
            "titulo": obj.servicio.titulo,
            "descripcion": obj.servicio.descripcion,
            "duracion": obj.servicio.duracion,
            "precio_usd": float(obj.servicio.precio_usd),
            "categoria": (
                obj.servicio.categoria.nombre if obj.servicio.categoria else None
            ),
            "imagen_url": obj.servicio.imagen_url,
            "estado": obj.servicio.estado,
            "servicios_incluidos": obj.servicio.servicios_incluidos,
        }

    def get_punto_encuentro_final(self, obj):
        """Punto de encuentro final (override o del servicio original)"""
        return obj.punto_encuentro_override or obj.servicio.punto_encuentro

class CampaniaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campania
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

class PaqueteSerializer(serializers.ModelSerializer):
    """Serializer completo para paquetes turísticos"""

    servicios_incluidos = serializers.SerializerMethodField()
    itinerario = serializers.SerializerMethodField()
    precios = serializers.SerializerMethodField()
    disponibilidad = serializers.SerializerMethodField()
    campania_info = serializers.SerializerMethodField()

    # CAMBIO: Remover el SerializerMethodField y usar el campo por defecto
    # proveedor = serializers.SerializerMethodField()  # ← ELIMINAR ESTA LÍNEA

    class Meta:
        model = Paquete
        fields = "__all__"
        read_only_fields = ["id", "created_at", "es_personalizado"]

    # ELIMINAR el método get_proveedor o cambiarlo por un campo de solo lectura
    # def get_proveedor(self, obj):
    #     if obj.proveedor:
    #         return {
    #             "id": obj.proveedor.id,
    #             "nombre": obj.proveedor.nombre,
    #             "telefono": obj.proveedor.telefono,
    #             "email": getattr(obj.proveedor, "user", None) and getattr(obj.proveedor.user, "email", None),
    #         }
    #     return None

    # Si necesitas la información del proveedor como solo lectura, usa otro nombre:
    proveedor_info = serializers.SerializerMethodField(read_only=True)



    def get_proveedor_info(self, obj):
        if obj.proveedor:
            return {
                "id": obj.proveedor.id,
                "nombre": obj.proveedor.nombre,
                "telefono": obj.proveedor.telefono,
                "email": getattr(obj.proveedor, "user", None) and getattr(obj.proveedor.user, "email", None),
            }
        return None

    def get_servicios_incluidos(self, obj):
        """Lista de servicios/destinos incluidos en el paquete"""
        paquete_servicios = PaqueteServicio.objects.filter(paquete=obj).select_related(
            "servicio__categoria"
        )
        servicios = set()  # Usar set para evitar duplicados

        for ps in paquete_servicios:
            servicio_data = {
                "id": ps.servicio.pk,
                "titulo": ps.servicio.titulo,
                "descripcion": ps.servicio.descripcion,
                "categoria": (
                    ps.servicio.categoria.nombre if ps.servicio.categoria else None
                ),
                "imagen_url": ps.servicio.imagen_url,
                "precio_usd": float(ps.servicio.precio_usd),
            }
            # Convertir a tuple para poder usar en set
            servicios.add(tuple(servicio_data.items()))

        # Convertir de vuelta a lista de diccionarios
        return [dict(s) for s in servicios]

    def get_itinerario(self, obj):
        """Itinerario completo organizado por días"""
        paquete_servicios = (
            PaqueteServicio.objects.filter(paquete=obj)
            .select_related("servicio__categoria")
            .order_by("dia", "orden")
        )

        itinerario = {}
        for ps in paquete_servicios:
            dia_key = f"dia_{ps.dia}"
            if dia_key not in itinerario:
                itinerario[dia_key] = {"dia": ps.dia, "actividades": []}

            itinerario[dia_key]["actividades"].append(
                {
                    "orden": ps.orden,
                    "hora_inicio": ps.hora_inicio,
                    "hora_fin": ps.hora_fin,
                    "titulo": ps.servicio.titulo,
                    "descripcion": ps.servicio.descripcion,
                    "punto_encuentro": ps.punto_encuentro_override
                    or ps.servicio.punto_encuentro,
                    "notas": ps.notas,
                    "categoria": (
                        ps.servicio.categoria.nombre if ps.servicio.categoria else None
                    ),
                }
            )

        return list(itinerario.values())

    def get_precios(self, obj):
        """Información de precios con descuentos aplicados"""
        precio_original = float(obj.precio_base)
        precio_final = float(obj.precio_con_descuento)

        return {
            "precio_original_usd": precio_original,
            "precio_final_usd": precio_final,
            "precio_bob": float(obj.precio_bob) if obj.precio_bob else None,
            "descuento_aplicado": (
                precio_original - precio_final if precio_final < precio_original else 0
            ),
            "porcentaje_descuento": (
                ((precio_original - precio_final) / precio_original * 100)
                if precio_final < precio_original
                else 0
            ),
        }

    def get_disponibilidad(self, obj):
        """Estado de disponibilidad del paquete"""
        return {
            "cupos_disponibles": obj.cupos_disponibles,
            "cupos_ocupados": obj.cupos_ocupados,
            "cupos_restantes": obj.cupos_restantes,
            "porcentaje_ocupacion": round(obj.porcentaje_ocupacion, 2),
            "esta_vigente": obj.esta_vigente,
            "esta_disponible": obj.esta_disponible,
            "fecha_inicio": obj.fecha_inicio,
            "fecha_fin": obj.fecha_fin,
        }

    def get_campania_info(self, obj):
        """Información de la campaña asociada si existe"""
        if not obj.campania:
            return None

        return {
            "id": obj.campania.pk,
            "nombre": obj.campania.nombre,
            "tipo_descuento": obj.campania.tipo_descuento,
            "monto": float(obj.campania.monto),
            "fecha_inicio": obj.campania.fecha_inicio,
            "fecha_fin": obj.campania.fecha_fin,
        }


# =====================================================
# 🎟️ CUPON
# =====================================================
class CuponSerializer(serializers.ModelSerializer):
    campania = CampaniaSerializer(read_only=True)
    campania_id = serializers.PrimaryKeyRelatedField(
        queryset=Campania.objects.all(), source="campania", write_only=True
    )

    class Meta:
        model = Cupon
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 🏞️ SERVICIO
# =====================================================
class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = "__all__"
        read_only_fields = ["id"]


# =====================================================
# 🧾 RESERVA
# =====================================================


class ReservaSerializer(serializers.ModelSerializer):
    cliente = UsuarioSerializer(read_only=True)
    cliente_id = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(), source="cliente", write_only=True
    )
    cupon = CuponSerializer(read_only=True)
    cupon_id = serializers.PrimaryKeyRelatedField(
        queryset=Cupon.objects.all(),
        source="cupon",
        write_only=True,
        required=False,
        allow_null=True,
    )

    # 🔹 Aquí añadimos los serializers anidados
    paquete = PaqueteSerializer(read_only=True)
    paquete_id = serializers.PrimaryKeyRelatedField(
        queryset=Paquete.objects.all(),
        source="paquete",
        write_only=True,
        required=False,
        allow_null=True,
    )

    servicio = ServicioSerializer(read_only=True)
    servicio_id = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(),
        source="servicio",
        write_only=True,
        required=False,
        allow_null=True,
    )

    reprogramado_por_nombre = serializers.CharField(
        source="reprogramado_por.nombre", read_only=True
    )

    class Meta:
        model = Reserva
        fields = "__all__"
        read_only_fields = [
            "id",
            "codigo",
            "reprogramado_por_nombre",
            "numero_reprogramaciones",
            "fecha_reprogramacion",
            "created_at",
            "updated_at",
        ]


# =====================================================
# 👥 VISITANTE
# =====================================================
class VisitanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitante
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 🔗 RESERVA_VISITANTE
# =====================================================
class ReservaVisitanteSerializer(serializers.ModelSerializer):
    reserva = ReservaSerializer(read_only=True)
    reserva_id = serializers.PrimaryKeyRelatedField(
        queryset=Reserva.objects.all(), source="reserva", write_only=True
    )
    visitante = VisitanteSerializer(read_only=True)
    visitante_id = serializers.PrimaryKeyRelatedField(
        queryset=Visitante.objects.all(), source="visitante", write_only=True
    )

    class Meta:
        model = ReservaVisitante
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 🔗 CAMPAÑA_SERVICIO
# =====================================================
class CampaniaServicioSerializer(serializers.ModelSerializer):
    servicio = ServicioSerializer(read_only=True)
    servicio_id = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(), source="servicio", write_only=True
    )
    campania = CampaniaSerializer(read_only=True)
    campania_id = serializers.PrimaryKeyRelatedField(
        queryset=Campania.objects.all(), source="campania", write_only=True
    )

    class Meta:
        model = CampaniaServicio
        fields = [
            "id",
            "created_at",
            "updated_at",
            "servicio",
            "servicio_id",
            "campania",
            "campania_id",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        servicio = attrs.get("servicio")
        campania = attrs.get("campania")
        if CampaniaServicio.objects.filter(
            servicio=servicio, campania=campania
        ).exists():
            raise serializers.ValidationError(
                "Esta relación de servicio y campaña ya existe."
            )
        return attrs


# =====================================================
# 💳 PAGO
# =====================================================
class PagoSerializer(serializers.ModelSerializer):
    reserva = ReservaSerializer(read_only=True)
    reserva_id = serializers.PrimaryKeyRelatedField(
        queryset=Reserva.objects.all(), source="reserva", write_only=True
    )

    class Meta:
        model = Pago
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


# =====================================================
# 🔁 REGLA_REPROGRAMACION
# =====================================================
class ReglaReprogramacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglaReprogramacion
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# =====================================================
# � HISTORIAL_REPROGRAMACION
# =====================================================
class HistorialReprogramacionSerializer(serializers.ModelSerializer):
    reserva_codigo = serializers.CharField(source="reserva.codigo", read_only=True)
    reprogramado_por_nombre = serializers.CharField(
        source="reprogramado_por.nombre", read_only=True
    )

    class Meta:
        model = HistorialReprogramacion
        fields = "__all__"
        read_only_fields = [
            "id",
            "reserva_codigo",
            "reprogramado_por_nombre",
            "created_at",
            "updated_at",
        ]


# =====================================================
# ⚙️ CONFIGURACION_GLOBAL_REPROGRAMACION
# =====================================================
class ConfiguracionGlobalReprogramacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionGlobalReprogramacion
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# =====================================================
#  REPROGRAMACION
# =====================================================
class ReprogramacionSerializer(serializers.ModelSerializer):
    reserva_codigo = serializers.CharField(source="reserva.codigo", read_only=True)
    solicitado_por_nombre = serializers.CharField(
        source="solicitado_por.nombre", read_only=True
    )
    aprobado_por_nombre = serializers.CharField(
        source="aprobado_por.nombre", read_only=True
    )

    class Meta:
        model = Reprogramacion
        fields = "__all__"
        read_only_fields = [
            "id",
            "reserva_codigo",
            "solicitado_por_nombre",
            "aprobado_por_nombre",
            "created_at",
            "updated_at",
        ]


# ==========================
# Soporte (Tickets)
# ==========================
class TicketMessageSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.nombre", read_only=True)

    class Meta:
        model = __import__(
            "condominio.models", fromlist=["TicketMessage"]
        ).TicketMessage
        fields = ["id", "ticket", "autor", "autor_nombre", "texto", "created_at"]
        read_only_fields = ["id", "created_at", "autor_nombre", "autor"]


class TicketSerializer(serializers.ModelSerializer):
    creador_nombre = serializers.CharField(source="creador.nombre", read_only=True)
    agente_nombre = serializers.CharField(source="agente.nombre", read_only=True)

    class Meta:
        model = __import__("condominio.models", fromlist=["Ticket"]).Ticket
        fields = [
            "id",
            "creador",
            "creador_nombre",
            "asunto",
            "descripcion",
            "estado",
            "agente",
            "agente_nombre",
            "prioridad",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "creador",
            "creador_nombre",
            "estado",
            "agente",
            "agente_nombre",
            "created_at",
            "updated_at",
        ]


class TicketDetailSerializer(TicketSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + ["messages"]


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = __import__("condominio.models", fromlist=["Notificacion"]).Notificacion
        fields = ["id", "usuario", "tipo", "datos", "leida", "created_at"]
        read_only_fields = ["id", "created_at"]


class BitacoraSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.nombre", read_only=True)
    actor_email = serializers.SerializerMethodField()
    created_at_local = serializers.SerializerMethodField()

    class Meta:
        model = __import__("condominio.models", fromlist=["Bitacora"]).Bitacora
        # include computed fields actor_email and created_at_local in the public fields
        fields = [
            "id",
            "usuario",
            "usuario_nombre",
            "actor_email",
            "accion",
            "descripcion",
            "ip_address",
            "created_at",
            "created_at_local",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "usuario_nombre",
            "created_at_local",
            "actor_email",
        ]

    def get_actor_email(self, obj):
        try:
            return (
                obj.usuario.user.email
                if obj.usuario and getattr(obj.usuario, "user", None)
                else None
            )
        except Exception:
            return None

    def get_created_at_local(self, obj):
        # Convert UTC time (stored) to America/La_Paz
        try:
            from django.utils import timezone
            from zoneinfo import ZoneInfo

            utc_dt = obj.created_at
            if utc_dt is None:
                return None
            if timezone.is_naive(utc_dt):
                # assume stored as UTC
                utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
            local_dt = utc_dt.astimezone(ZoneInfo("America/La_Paz"))
            return local_dt.isoformat()
        except Exception:
            return str(obj.created_at)
        
# ==========================
# Comprobante de Pago
# ==========================      
        
class ComprobantePagoSerializer(serializers.ModelSerializer):
    reserva_detalle = serializers.StringRelatedField(source='reserva', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)

    class Meta:
        model = ComprobantePago
        fields = '__all__'


# ==========================
# SERIALIZERS DESHABILITADOS
# ==========================
# Los siguientes serializers están comentados porque sus modelos fueron
# eliminados en la migración 0009 (Proveedor, Suscripcion, CampanaNotificacion).
# Si en el futuro se necesitan estas funcionalidades, será necesario:
# 1. Restaurar los modelos en condominio/models.py
# 2. Crear migraciones para agregar las tablas a la BD
# 3. Descomentar estos serializers

# class ProveedorSerializer(serializers.ModelSerializer):
#     # Campo para escritura (solo el id del usuario)
#     usuario_id = serializers.PrimaryKeyRelatedField(
#         queryset=Usuario.objects.all(), source="usuario", write_only=True
#     )
#     # Campo para lectura (expandido con datos del usuario)
#     usuario = UsuarioSerializer(read_only=True)
#
#     class Meta:
#         model = Proveedor
#         fields = "__all__"
#         read_only_fields = ["id", "created_at", "updated_at"]

# class SuscripcionSerializer(serializers.ModelSerializer):
#     proveedor = ProveedorSerializer(read_only=True)
#     proveedor_id = serializers.PrimaryKeyRelatedField(
#         queryset=Proveedor.objects.all(), source="proveedor", write_only=True
#     )
#
#     class Meta:
#         model = Suscripcion
#         fields = "__all__"
#         read_only_fields = ["id", "created_at", "updated_at"]


# =====================================================
# 📱 DISPOSITIVOS FCM
# =====================================================

class FCMDeviceSerializer(serializers.ModelSerializer):
    """Serializer para dispositivos FCM."""
    
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    
    class Meta:
        model = FCMDevice
        fields = [
            'id',
            'usuario',
            'usuario_nombre',
            'registration_id',
            'tipo_dispositivo',
            'nombre',
            'activo',
            'created_at',
            'ultima_vez'
        ]
        read_only_fields = ['id', 'created_at', 'ultima_vez', 'usuario_nombre']


# =====================================================
# �📢 CAMPAÑA DE NOTIFICACIONES
# =====================================================
class CampanaNotificacionSerializer(serializers.ModelSerializer):
    """Serializer completo para campañas de notificación."""
    
    usuarios_objetivo_detalle = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    tipo_audiencia_display = serializers.CharField(source='get_tipo_audiencia_display', read_only=True)
    
    class Meta:
        model = CampanaNotificacion
        fields = [
            'id',
            'nombre',
            'descripcion',
            'titulo',
            'cuerpo',
            'datos_extra',
            'tipo_notificacion',
            'tipo_audiencia',
            'tipo_audiencia_display',
            'usuarios_objetivo',
            'usuarios_objetivo_detalle',
            'segmento_filtros',
            'estado',
            'estado_display',
            'enviar_inmediatamente',
            'fecha_programada',
            'fecha_enviada',
            'total_destinatarios',
            'total_enviados',
            'total_errores',
            'resultado',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'estado_display',
            'tipo_audiencia_display',
            'fecha_enviada',
            'total_destinatarios',
            'total_enviados',
            'total_errores',
            'resultado',
            'created_at',
            'updated_at'
        ]
    
    def get_usuarios_objetivo_detalle(self, obj):
        """Retorna información básica de usuarios objetivo (solo primeros 10)."""
        if obj.tipo_audiencia == 'USUARIOS':
            usuarios = obj.usuarios_objetivo.all()[:10]
            return [
                {
                    'id': u.id,
                    'nombre': u.nombre,
                    'email': u.user.email if hasattr(u, 'user') else None
                }
                for u in usuarios
            ]
        return []
    
    def validate(self, data):
        """Validaciones personalizadas."""
        # Si es programada, debe tener fecha
        if not data.get('enviar_inmediatamente') and not data.get('fecha_programada'):
            raise serializers.ValidationError(
                'Debe especificar fecha_programada si no es envío inmediato'
            )
        
        # Si es USUARIOS, debe tener usuarios
        if data.get('tipo_audiencia') == 'USUARIOS':
            usuarios = data.get('usuarios_objetivo', [])
            if not usuarios:
                raise serializers.ValidationError(
                    'Debe seleccionar al menos un usuario para tipo_audiencia=USUARIOS'
                )
        
        return data

class ProveedorSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(), source="usuario", write_only=True
    )
    # Campo para lectura (expandido con datos del usuario)

    class Meta:
        model = Proveedor
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class SuscripcionSerializer(serializers.ModelSerializer):
    proveedor = ProveedorSerializer(read_only=True)
    proveedor_id = serializers.PrimaryKeyRelatedField(
        queryset=Proveedor.objects.all(), source="proveedor", write_only=True
    )
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), source="plan", write_only=True
    )
    class Meta:
        model = Suscripcion
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]





