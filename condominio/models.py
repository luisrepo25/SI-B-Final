from django.db import models
from decimal import Decimal

from authz.models import Rol
from core.models import TimeStampedModel
from django.contrib.auth.models import User
# Create your models here.


from django.db import models
# ======================================
# 🧍 Rol
# ====================================== 

# ======================================
# 🧍 USUARIO
# ======================================
class Usuario(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    nombre = models.CharField(max_length=100)
    rubro = models.CharField(max_length=100, blank=True, null=True)
    num_viajes = models.PositiveIntegerField(default=0)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    # Campos opcionales solicitados por frontend
    telefono = models.CharField(max_length=50, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    genero = models.CharField(max_length=5, blank=True, null=True)
    documento_identidad = models.CharField(max_length=100, blank=True, null=True)
    pais = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre}"
    

# ======================================
# 🏷️ CATEGORIA
# ======================================
class Categoria(TimeStampedModel):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


# ======================================
# 🎯 CAMPAÑA
# ======================================
class Campania(TimeStampedModel):
    descripcion = models.CharField(max_length=200)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_descuento = models.CharField(max_length=5, choices=[('%', 'Porcentaje'), ('$', 'Monto fijo')])
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.descripcion} ({self.tipo_descuento}{self.monto})"


# ======================================
# 🎟️ CUPON
# ======================================
class Cupon(TimeStampedModel):
    nro_usos = models.PositiveIntegerField(default=0)
    cantidad_max = models.PositiveIntegerField(default=0)
    campania = models.ForeignKey(Campania, on_delete=models.CASCADE, related_name='cupones')

    def __str__(self):
        return f"Cupón #{self.pk or 'Nuevo'} ({self.nro_usos}/{self.cantidad_max})"


# ======================================
# 🧾 RESERVA
# ======================================
class Reserva(TimeStampedModel):
    id = models.AutoField(primary_key=True)
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADA', 'Confirmada'), 
        ('PAGADA', 'Pagada'),
        ('CANCELADA', 'Cancelada'),
        ('COMPLETADA', 'Completada'),
        ('REPROGRAMADA', 'Reprogramada'),
    ]
    
    fecha = models.DateField()
    fecha_inicio = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora específica del servicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora de finalización")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=10, default='BOB')
    cliente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='reservas')
    cupon = models.ForeignKey(Cupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas')
    servicio = models.ForeignKey('Servicio', on_delete=models.CASCADE, related_name='reservas', null=True, blank=True)
    paquete = models.ForeignKey('Paquete', on_delete=models.CASCADE, related_name='reservas', null=True, blank=True)
    # 🔄 Campos para reprogramación
    fecha_original = models.DateTimeField(null=True, blank=True, help_text="Fecha original antes de reprogramar")
    fecha_reprogramacion = models.DateTimeField(null=True, blank=True, help_text="Última fecha de reprogramación")
    numero_reprogramaciones = models.IntegerField(default=0, help_text="Cantidad de veces reprogramada")
    motivo_reprogramacion = models.CharField(max_length=255, blank=True, null=True)
    reprogramado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='reprogramaciones_realizadas')

    def __str__(self):
        return f"Reserva #{self.pk} - {self.cliente.nombre}"


# ======================================
# 📅 HISTORIAL REPROGRAMACION
# ======================================
class HistorialReprogramacion(TimeStampedModel):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='historial_reprogramaciones')
    fecha_anterior = models.DateTimeField(help_text="Fecha anterior antes del cambio")
    fecha_nueva = models.DateTimeField(help_text="Nueva fecha después del cambio")
    motivo = models.TextField(blank=True, null=True, help_text="Motivo de la reprogramación")
    reprogramado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    notificacion_enviada = models.BooleanField(default=False, help_text="Si se envió notificación al cliente")

    class Meta(TimeStampedModel.Meta):
        ordering = ['-created_at']
        verbose_name = "Historial de Reprogramación"
        verbose_name_plural = "Historial de Reprogramaciones"

    def __str__(self):
        return f"Historial Reserva #{self.reserva.pk} - {self.fecha_nueva.strftime('%d/%m/%Y')}"


# ======================================
# 👥 VISITANTE
# ======================================
class Visitante(TimeStampedModel):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nac = models.DateField()
    nacionalidad = models.CharField(max_length=100)
    nro_doc = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    es_titular = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# ======================================
# 🔗 RESERVA_VISITANTE (intermedia muchos a muchos)
# ======================================
class ReservaVisitante(TimeStampedModel):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='visitantes')
    visitante = models.ForeignKey(Visitante, on_delete=models.CASCADE, related_name='reservas')

    class Meta(TimeStampedModel.Meta):
        unique_together = ('reserva', 'visitante')

    def __str__(self):
        return f"Reserva {self.reserva.pk or 'Nueva'} - {self.visitante.nombre}"

# ======================================
# 🔗 RESERVA_SERVICIO (servicios múltiples por reserva)
# ======================================
class ReservaServicio(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='servicios_reservados')
    servicio = models.ForeignKey('Servicio', on_delete=models.CASCADE)
    fecha = models.DateField()
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reserva} - {self.servicio.titulo} ({self.fecha})"


# ======================================
# 🏞️ SERVICIO
# ======================================


class Servicio(TimeStampedModel):
    ESTADOS = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
    ]

    titulo = models.CharField(max_length=255)
    descripcion = models.TextField()
    duracion = models.CharField(max_length=50)
    capacidad_max = models.IntegerField()
    punto_encuentro = models.CharField(max_length=255)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='Activo')
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, null=True, blank=True)
    proveedor = models.ForeignKey(Usuario, on_delete=models.CASCADE, null=True, blank=True)

    imagen_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL de la imagen representativa del servicio"
    )
    precio_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Precio en dólares del servicio"
    )
    servicios_incluidos = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de servicios incluidos (ej: Guía, Transporte, Hotel)"
    )
    
    # Ubicación geográfica
    departamento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Departamento donde se realiza el servicio"
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Ciudad donde se realiza el servicio"
    )

    def __str__(self):
        return self.titulo


# ======================================
# 📦 PAQUETE TURÍSTICO
# ======================================
class Paquete(TimeStampedModel):
    ESTADOS = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
        ('Agotado', 'Agotado'),
    ]
    
    nombre = models.CharField(max_length=200, help_text="Nombre del paquete turístico")
    es_personalizado = models.BooleanField(default=False, help_text="Indica si el paquete fue creado por el usuario")
    descripcion = models.TextField(help_text="Descripción detallada del paquete")
    duracion = models.CharField(max_length=50, help_text="Duración total del paquete (ej: 3 días, 1 semana)")
    
    # Servicios/Destinos incluidos en el paquete
    servicios = models.ManyToManyField(
        Servicio, 
        through='PaqueteServicio', 
        related_name='paquetes',
        help_text="Servicios/destinos incluidos en este paquete"
    )
    
    # Precios y disponibilidad
    precio_base = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Precio base del paquete completo en USD"
    )
    precio_bob = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Precio en bolivianos (se calcula automáticamente)"
    )
    
    # Disponibilidad
    cupos_disponibles = models.PositiveIntegerField(
        default=20, 
        help_text="Número de cupos disponibles para este paquete"
    )
    cupos_ocupados = models.PositiveIntegerField(
        default=0,
        help_text="Número de cupos ya reservados"
    )
    
    # Fechas de vigencia
    fecha_inicio = models.DateField(help_text="Fecha de inicio de disponibilidad")
    fecha_fin = models.DateField(help_text="Fecha de fin de disponibilidad")
    
    # Estado y configuración
    estado = models.CharField(max_length=10, choices=ESTADOS, default='Activo')
    destacado = models.BooleanField(default=False, help_text="Mostrar como paquete destacado")
    
    # Información adicional
    imagen_principal = models.URLField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="URL de la imagen principal del paquete"
    )
    punto_salida = models.CharField(
        max_length=255, 
        help_text="Punto de salida del paquete turístico"
    )
    incluye = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de lo que incluye el paquete (transporte, hotel, guía, etc.)"
    )
    no_incluye = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de lo que NO incluye el paquete"
    )
    
    # Campaña asociada (opcional para descuentos)
    campania = models.ForeignKey(
        'Campania', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paquetes_con_descuento',
        help_text="Campaña de descuento aplicable a este paquete"
    )
    
    # Ubicación geográfica
    departamento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Departamento principal del paquete turístico"
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Ciudad principal del paquete turístico"
    )
    tipo_destino = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('Cultural', 'Cultural'),
            ('Natural', 'Natural'),
            ('Aventura', 'Aventura'),
            ('Rural', 'Rural'),
            ('Urbano', 'Urbano'),
        ],
        help_text="Tipo de destino turístico"
    )

    class Meta(TimeStampedModel.Meta):
        ordering = ['-destacado', '-created_at']
        verbose_name = "Paquete Turístico"
        verbose_name_plural = "Paquetes Turísticos"

    def __str__(self):
        return f"{self.nombre} ({self.duracion})"
    
    @property
    def cupos_restantes(self):
        """Cupos disponibles restantes"""
        return max(0, self.cupos_disponibles - self.cupos_ocupados)
    
    @property
    def porcentaje_ocupacion(self):
        """Porcentaje de ocupación del paquete"""
        if self.cupos_disponibles == 0:
            return 0
        return (self.cupos_ocupados / self.cupos_disponibles) * 100
    
    @property
    def precio_con_descuento(self):
        """Precio final aplicando descuento de campaña si existe"""
        if not self.campania:
            return self.precio_base
        
        if self.campania.tipo_descuento == '%':
            descuento = self.precio_base * (self.campania.monto / 100)
            return self.precio_base - descuento
        else:  # Descuento fijo
            return max(0, self.precio_base - self.campania.monto)
    
    @property
    def esta_vigente(self):
        """Verifica si el paquete está vigente hoy"""
        from django.utils import timezone
        hoy = timezone.now().date()
        return self.fecha_inicio <= hoy <= self.fecha_fin
    
    @property
    def esta_disponible(self):
        """Verifica si el paquete está disponible para reservar"""
        return (
            self.estado == 'Activo' and 
            self.esta_vigente and 
            self.cupos_restantes > 0
        )


# ======================================
# 🔗 PAQUETE_SERVICIO (tabla intermedia)
# ======================================
class PaqueteServicio(TimeStampedModel):
    """Tabla intermedia entre Paquete y Servicio con información adicional"""
    
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    
    # Información específica del servicio en este paquete
    dia = models.PositiveIntegerField(help_text="Día del itinerario (1, 2, 3, etc.)")
    orden = models.PositiveIntegerField(default=1, help_text="Orden dentro del día")
    
    # Horarios específicos para este paquete
    hora_inicio = models.TimeField(null=True, blank=True, help_text="Hora de inicio del servicio")
    hora_fin = models.TimeField(null=True, blank=True, help_text="Hora de finalización del servicio")
    
    # Notas específicas
    notas = models.TextField(
        blank=True, 
        null=True, 
        help_text="Notas específicas del servicio en este paquete"
    )
    
    # Opcional: Override del punto de encuentro para este paquete
    punto_encuentro_override = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Punto de encuentro específico para este paquete (si difiere del servicio)"
    )
    
    class Meta(TimeStampedModel.Meta):
        unique_together = ('paquete', 'servicio', 'dia', 'orden')
        ordering = ['dia', 'orden']
        verbose_name = "Servicio en Paquete"
        verbose_name_plural = "Servicios en Paquetes"
    
    def __str__(self):
        return f"{self.paquete.nombre} - Día {self.dia}: {self.servicio.titulo}"


# ======================================
# 🔗 CAMPAÑA_SERVICIO (intermedia muchos a muchos)
# ======================================
class CampaniaServicio(TimeStampedModel):
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='campanias')
    campania = models.ForeignKey(Campania, on_delete=models.CASCADE, related_name='servicios')

    class Meta(TimeStampedModel.Meta):
        unique_together = ('servicio', 'campania')

    def __str__(self):
        return f"{self.servicio.titulo} -> {self.campania.descripcion}"


# ======================================
# 💳 PAGO
# ======================================
class Pago(TimeStampedModel):
    METODOS = [
        ('Tarjeta', 'Tarjeta'),
        ('Transferencia', 'Transferencia'),
        ('Efectivo', 'Efectivo'),
    ]
    ESTADOS = [
        ('Confirmado', 'Confirmado'),
        ('Pendiente', 'Pendiente'),
        ('Fallido', 'Fallido'),
    ]

    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODOS)
    fecha_pago = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS)
    url_stripe = models.URLField(max_length=255, blank=True, null=True)
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='pagos')

    def __str__(self):
        return f"Pago {self.pk or 'Nuevo'} - {self.estado} - {self.monto}"


# ======================================
# ⚙️ REGLAS_REPROGRAMACION (Avanzadas)
# ======================================
class ReglaReprogramacion(TimeStampedModel):
    TIPOS_REGLA = [
        ('TIEMPO_MINIMO', 'Tiempo mínimo de anticipación'),
        ('TIEMPO_MAXIMO', 'Tiempo máximo para reprogramar'),
        ('LIMITE_REPROGRAMACIONES', 'Límite de reprogramaciones por reserva'),
        ('LIMITE_DIARIO', 'Límite diario de reprogramaciones por usuario'),
        ('DIAS_BLACKOUT', 'Días no permitidos para reprogramar'),
        ('HORAS_BLACKOUT', 'Horas no permitidas'),
        ('SERVICIOS_RESTRINGIDOS', 'Servicios con restricciones especiales'),
        ('CAPACIDAD_MAXIMA', 'Límite de capacidad por fecha'),
        ('DESCUENTO_PENALIZACION', 'Penalización por reprogramar'),
    ]
    
    APLICABLE_A = [
        ('ALL', 'Todos los usuarios'),
        ('CLIENTE', 'Solo clientes'),
        ('ADMIN', 'Solo administradores'),
        ('OPERADOR', 'Solo operadores'),
    ]
    
    nombre = models.CharField(max_length=200, default="Regla sin nombre", help_text="Nombre descriptivo de la regla")
    tipo_regla = models.CharField(max_length=50, choices=TIPOS_REGLA, default='TIEMPO_ANTICIPACION')
    aplicable_a = models.CharField(max_length=50, choices=APLICABLE_A, default='ALL')
    descripcion = models.CharField(max_length=150, default="Descripción pendiente")
    limite_hora = models.PositiveIntegerField(help_text="Horas antes del evento para permitir reprogramación", null=True, blank=True)
    condiciones = models.TextField(blank=True, null=True)
    
    # 🔢 Valores dinámicos por tipo de regla  
    valor_numerico = models.IntegerField(null=True, blank=True, help_text="Para límites numéricos")
    valor_decimal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Para porcentajes y decimales")
    valor_texto = models.TextField(null=True, blank=True, help_text="Para listas, JSON, etc.")
    valor_booleano = models.BooleanField(null=True, blank=True, help_text="Para reglas si/no")
    
    # 📅 Vigencia de la regla
    fecha_inicio_vigencia = models.DateField(null=True, blank=True)
    fecha_fin_vigencia = models.DateField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    prioridad = models.IntegerField(default=0, help_text="Mayor número = mayor prioridad")
    
    # 📝 Configuración avanzada
    mensaje_error = models.TextField(null=True, blank=True, help_text="Mensaje personalizado cuando no se cumple")
    condiciones_extras = models.JSONField(default=dict, blank=True, help_text="Condiciones adicionales en JSON")

    class Meta(TimeStampedModel.Meta):
        ordering = ['-prioridad', '-created_at']
        verbose_name = "Regla de Reprogramación"
        verbose_name_plural = "Reglas de Reprogramación"

    def obtener_valor(self):
        """Retorna el valor apropiado según el tipo de datos configurado"""
        if self.valor_numerico is not None:
            return self.valor_numerico
        if self.valor_decimal is not None:
            return self.valor_decimal
        if self.valor_texto:
            return self.valor_texto
        if self.valor_booleano is not None:
            return self.valor_booleano
        return None
    
    @classmethod
    def obtener_regla_activa(cls, tipo_regla, rol='ALL'):
        """Obtiene la regla activa de mayor prioridad para el tipo y rol dados"""
        return cls.objects.filter(
            tipo_regla=tipo_regla,
            aplicable_a=rol,
            activa=True
        ).order_by('-prioridad', '-created_at').first()
    
    @classmethod
    def obtener_valor_regla(cls, tipo_regla, rol='ALL', default=None):
        """Obtiene directamente el valor de una regla"""
        regla = cls.obtener_regla_activa(tipo_regla, rol)
        if regla:
            return regla.obtener_valor()
        return default

    def __str__(self):
        return f"{self.nombre} ({self.tipo_regla}) - {self.aplicable_a}"


# ======================================
# ⚙️ CONFIGURACION_GLOBAL_REPROGRAMACION
# ======================================
class ConfiguracionGlobalReprogramacion(TimeStampedModel):
    TIPOS_VALOR = [
        ('STRING', 'Texto'),
        ('INTEGER', 'Número entero'),
        ('DECIMAL', 'Número decimal'),
        ('BOOLEAN', 'Verdadero/Falso'),
        ('JSON', 'Objeto JSON'),
        ('LISTA', 'Lista separada por comas'),
    ]
    
    clave = models.CharField(max_length=100, unique=True, help_text="Identificador único de la configuración")
    valor = models.TextField(help_text="Valor de la configuración")
    tipo_valor = models.CharField(max_length=50, choices=TIPOS_VALOR, default='STRING')
    activa = models.BooleanField(default=True)
    descripcion = models.TextField(null=True, blank=True, help_text="Descripción de qué hace esta configuración")

    class Meta(TimeStampedModel.Meta):
        ordering = ['clave']
        verbose_name = "Configuración Global"
        verbose_name_plural = "Configuraciones Globales"

    def obtener_valor_tipado(self):
        """Convierte el valor según su tipo configurado"""
        import json
        
        tipo = self.tipo_valor.upper() if self.tipo_valor else 'STRING'
        valor = self.valor

        if tipo == 'INTEGER':
            try:
                return int(valor)
            except (ValueError, TypeError):
                return valor
        elif tipo == 'DECIMAL':
            try:
                return float(valor)
            except (ValueError, TypeError):
                return valor
        elif tipo == 'BOOLEAN':
            return str(valor).lower() in ['true', '1', 'yes', 'si']
        elif tipo == 'JSON':
            try:
                return json.loads(valor)
            except (ValueError, TypeError):
                return valor
        elif tipo == 'LISTA':
            return [v.strip() for v in valor.split(',')]
        return valor

    @classmethod
    def obtener_configuracion(cls, clave, default=None):
        """Obtiene una configuración por su clave"""
        try:
            config = cls.objects.get(clave=clave, activa=True)
            return config.obtener_valor_tipado()
        except cls.DoesNotExist:
            return default

    def __str__(self):
        return f"{self.clave}: {self.valor[:50]}..."


# ======================================
# 🔄 REPROGRAMACION
# ======================================
class Reprogramacion(TimeStampedModel):
    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('Aprobado', 'Aprobado'),
        ('Rechazada', 'Rechazada'),
    ]
    TIPOS = [
        ('Voluntaria', 'Voluntaria'),
        ('Forzada', 'Forzada'),
    ]

    fecha_solicitud = models.DateField()
    nueva_fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='reprogramaciones')

    def __str__(self):
        return f"Reprogramación {self.pk or 'Nueva'} ({self.estado})"


# ======================================
# 🆘 SOPORTE / TICKETS (CU17)
# Minimal models required for soporte (no relación con Reserva)
# ======================================
class Ticket(TimeStampedModel):
    ESTADOS = [
        ('Abierto', 'Abierto'),
        ('Asignado', 'Asignado'),
        ('Respondido', 'Respondido'),
        ('Cerrado', 'Cerrado'),
    ]

    creador = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tickets_creados')
    asunto = models.CharField(max_length=150)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Abierto')
    agente = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_asignados')
    prioridad = models.CharField(max_length=10, blank=True, null=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.pk or 'Nuevo'} - {self.asunto} ({self.estado})"


class TicketMessage(TimeStampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    autor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_soporte')
    texto = models.TextField()

    def __str__(self):
        return f"Mensaje #{self.pk or 'Nuevo'} - Ticket {self.ticket.pk or 'Nuevo'} by {self.autor.nombre}"


class Notificacion(TimeStampedModel):
    TIPOS = [
        ('ticket_nuevo', 'Ticket Nuevo'),
        ('ticket_respondido', 'Ticket Respondido'),
        ('ticket_cerrado', 'Ticket Cerrado'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=50, choices=TIPOS)
    datos = models.JSONField(blank=True, null=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificación #{self.pk or 'Nueva'} -> {self.usuario.nombre} ({self.tipo})"


# ======================================
# Bitacora / Log de acciones
# ======================================
class Bitacora(TimeStampedModel):
    """Registro de acciones realizadas en el sistema.
    Guarda referencia al perfil (Usuario) cuando aplica, la accion, descripcion libre,
    y la IP de la máquina que realizó la acción.
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='bitacoras')
    accion = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)

    def __str__(self):
        who = self.usuario.nombre if self.usuario else 'Anon'
        fecha = self.created_at.isoformat() if self.created_at else 'Sin fecha'
        return f"{fecha} - {who} - {self.accion}"

# ======================================
# 🧾 COMPROBANTE DE PAGO (CU10 - Cliente)
# ======================================
class ComprobantePago(TimeStampedModel):
    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('Verificado', 'Verificado'),
        ('Rechazado', 'Rechazado'),
    ]
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='comprobantes')
    cliente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='comprobantes')
    metodo_pago = models.CharField(max_length=50, choices=Pago.METODOS, default='Transferencia')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    archivo = models.FileField(upload_to='comprobantes/', null=True, blank=True)
    numero_transaccion = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente')
    observacion = models.TextField(blank=True, null=True, help_text="Comentario del administrador (si es rechazado o revisado)")

    class Meta(TimeStampedModel.Meta):
        ordering = ['-created_at']
        verbose_name = "Comprobante de Pago"
        verbose_name_plural = "Comprobantes de Pago"

    def __str__(self):
        return f"Comprobante #{self.pk or 'Nuevo'} - {self.reserva} - {self.estado}"


# ============================================
# 📱 DISPOSITIVOS FCM (Firebase Cloud Messaging)
# ============================================
class FCMDevice(models.Model):
    """
    Dispositivos móviles registrados para recibir notificaciones push.
    Cada usuario puede tener múltiples dispositivos (ej: teléfono + tablet).
    """
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name='dispositivos_fcm',
        help_text='Usuario propietario del dispositivo'
    )
    registration_id = models.TextField(
        unique=True,
        help_text='Token FCM único del dispositivo'
    )
    tipo_dispositivo = models.CharField(
        max_length=20, 
        choices=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web')
        ],
        default='android',
        help_text='Tipo de dispositivo'
    )
    nombre = models.CharField(
        max_length=100, 
        blank=True,
        help_text='Nombre descriptivo (ej: "Celular de Juan")'
    )
    activo = models.BooleanField(
        default=True,
        help_text='Si está activo para recibir notificaciones'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    ultima_vez = models.DateTimeField(
        auto_now=True,
        help_text='Última vez que se actualizó el token'
    )

    class Meta:
        verbose_name = 'Dispositivo FCM'
        verbose_name_plural = 'Dispositivos FCM'
        ordering = ['-ultima_vez']

    def __str__(self):
        return f"{self.usuario.nombre} - {self.tipo_dispositivo} ({self.id})"


# ============================================
# 📢 CAMPAÑAS DE NOTIFICACIONES
# ============================================
class CampanaNotificacion(models.Model):
    """
    Campañas de notificaciones push masivas o segmentadas.
    Permite envío inmediato o programado.
    """
    
    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('PROGRAMADA', 'Programada'),
        ('EN_CURSO', 'En Curso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('ERROR', 'Error'),
    ]
    
    TIPOS_AUDIENCIA = [
        ('TODOS', 'Todos los usuarios'),
        ('USUARIOS', 'Usuarios específicos'),
        ('SEGMENTO', 'Segmento por filtros'),
        ('ROL', 'Por rol'),
    ]
    
    TIPOS_NOTIFICACION = [
        ('informativa', 'Informativa'),
        ('promocional', 'Promocional'),
        ('urgente', 'Urgente'),
        ('campana_marketing', 'Campaña Marketing'),
        ('actualizacion_sistema', 'Actualización Sistema'),
    ]
    
    # Información básica
    nombre = models.CharField(
        max_length=200,
        help_text='Nombre interno de la campaña'
    )
    descripcion = models.TextField(
        blank=True,
        help_text='Descripción interna (no se envía)'
    )
    
    # Contenido de la notificación
    titulo = models.CharField(
        max_length=100,
        help_text='Título que verá el usuario (máx 100 caracteres)'
    )
    cuerpo = models.TextField(
        max_length=500,
        help_text='Mensaje que verá el usuario (máx 500 caracteres)'
    )
    
    # Datos adicionales (JSON)
    datos_extra = models.JSONField(
        default=dict,
        blank=True,
        help_text='Datos adicionales para la app (acción, URL, etc.)'
    )
    
    # Clasificación
    tipo_notificacion = models.CharField(
        max_length=50,
        choices=TIPOS_NOTIFICACION,
        default='informativa'
    )
    
    # Segmentación
    tipo_audiencia = models.CharField(
        max_length=20,
        choices=TIPOS_AUDIENCIA,
        default='TODOS'
    )
    usuarios_objetivo = models.ManyToManyField(
        Usuario,
        blank=True,
        related_name='campanas_notificacion',
        help_text='Usuarios específicos (si tipo_audiencia=USUARIOS)'
    )
    segmento_filtros = models.JSONField(
        default=dict,
        blank=True,
        help_text='Filtros de segmentación (rol, num_viajes, etc.)'
    )
    
    # Programación
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='BORRADOR'
    )
    enviar_inmediatamente = models.BooleanField(
        default=True,
        help_text='Si es True, se envía al activar. Si es False, usar fecha_programada'
    )
    fecha_programada = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha y hora de envío programado'
    )
    fecha_enviada = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Fecha y hora en que se completó el envío'
    )
    
    # Resultados
    total_destinatarios = models.IntegerField(
        default=0,
        help_text='Número de destinatarios objetivo'
    )
    total_enviados = models.IntegerField(
        default=0,
        help_text='Notificaciones enviadas exitosamente'
    )
    total_errores = models.IntegerField(
        default=0,
        help_text='Notificaciones con error'
    )
    resultado = models.JSONField(
        default=dict,
        blank=True,
        help_text='Detalles completos del envío'
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Campaña de Notificación'
        verbose_name_plural = 'Campañas de Notificación'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"
    
    def puede_activarse(self):
        """Verifica si la campaña puede ser activada."""
        return self.estado in ['BORRADOR', 'PROGRAMADA']
    
    def puede_cancelarse(self):
        """Verifica si la campaña puede ser cancelada."""
        return self.estado in ['BORRADOR', 'PROGRAMADA']
    
    def calcular_destinatarios(self):
        """Calcula el número de destinatarios según la segmentación."""
        usuarios = self.obtener_usuarios_objetivo()
        self.total_destinatarios = usuarios.count()
        self.save(update_fields=['total_destinatarios'])
        return self.total_destinatarios
    
    def obtener_usuarios_objetivo(self):
        """Retorna QuerySet de usuarios que recibirán la notificación."""
        if self.tipo_audiencia == 'TODOS':
            return Usuario.objects.filter(user__is_active=True)
        
        elif self.tipo_audiencia == 'USUARIOS':
            return self.usuarios_objetivo.filter(user__is_active=True)
        
        elif self.tipo_audiencia == 'SEGMENTO':
            usuarios = Usuario.objects.filter(user__is_active=True)
            
            # Aplicar filtros del segmento
            if 'rol' in self.segmento_filtros:
                usuarios = usuarios.filter(rol__nombre=self.segmento_filtros['rol'])
            
            if 'min_viajes' in self.segmento_filtros:
                usuarios = usuarios.filter(num_viajes__gte=self.segmento_filtros['min_viajes'])
            
            return usuarios
        
        elif self.tipo_audiencia == 'ROL':
            rol_nombre = self.segmento_filtros.get('rol')
            if rol_nombre:
                return Usuario.objects.filter(user__is_active=True, rol__nombre=rol_nombre)
        
        return Usuario.objects.none()


# ============================
# PROVEEDORES TURÍSTICOS
# ============================
class Proveedor(TimeStampedModel):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="proveedor")
    nombre_empresa = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    sitio_web = models.URLField(blank=True)

    def __str__(self):
        return self.nombre_empresa


# ============================
# SUSCRIPCIONES DE PROVEEDORES
# ============================
class Suscripcion(TimeStampedModel):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="suscripciones")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activa = models.BooleanField(default=True)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self):
        return f"{self.proveedor} → {self.plan}"

    def esta_vigente(self):
        from django.utils import timezone
        hoy = timezone.now().date()
        return self.activa and self.fecha_inicio <= hoy <= self.fecha_fin
