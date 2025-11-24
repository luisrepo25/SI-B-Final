"""
Comando Django para generar datos históricos sintéticos de prueba para reportes.
Genera datos realistas con patrones de temporadas, tendencias y variabilidad.
Versión 3.0: Genera 1500+ reservas en 2 años con todos los departamentos

Uso: 
    python manage.py generar_datos_historicos
    python manage.py generar_datos_historicos --meses=24 --cantidad=65
    python manage.py generar_datos_historicos --limpiar  # Limpia datos anteriores
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, date, datetime
from decimal import Decimal
import random
import string

from condominio.models import (
    Usuario, Servicio, Paquete, Reserva, Pago, 
    Categoria, Visitante, ReservaVisitante, ReservaServicio
)
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Genera datos históricos sintéticos de prueba para reportes - 2 AÑOS COMPLETOS (1500+ reservas)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--meses',
            type=int,
            default=24,  # 2 años por defecto
            help='Número de meses hacia atrás para generar datos (default: 24 = 2 años)'
        )
        parser.add_argument(
            '--cantidad',
            type=int,
            default=65,  # 65 reservas/mes * 24 meses = ~1560 reservas
            help='Cantidad de reservas a generar por mes (default: 65)'
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina datos de prueba existentes antes de generar nuevos'
        )

    def handle(self, *args, **options):
        meses = options['meses']
        cantidad_por_mes = options['cantidad']
        limpiar = options.get('limpiar', False)
        
        self.stdout.write(self.style.SUCCESS(f'=' * 80))
        self.stdout.write(self.style.SUCCESS(f'🚀 GENERADOR DE DATOS SINTÉTICOS V3.0 - 2 AÑOS COMPLETOS'))
        self.stdout.write(self.style.SUCCESS(f'=' * 80))
        
        if limpiar:
            self.stdout.write(self.style.WARNING('\n🗑️  Limpiando datos de prueba existentes...'))
            self._limpiar_datos()
            self.stdout.write(self.style.SUCCESS('✅ Datos anteriores eliminados\n'))
        
        # Calcular rango de fechas
        fecha_fin = timezone.now().date()
        fecha_inicio = fecha_fin - timedelta(days=30 * meses)
        
        self.stdout.write(f'\n📊 Configuración:')
        self.stdout.write(f'   - Período: {fecha_inicio} hasta {fecha_fin}')
        self.stdout.write(f'   - Meses: {meses} ({meses/12:.1f} años)')
        self.stdout.write(f'   - Reservas por mes: {cantidad_por_mes}')
        self.stdout.write(f'   - Total estimado: {meses * cantidad_por_mes} reservas')
        self.stdout.write(f'   - 9 departamentos de Bolivia con datos\n')
        
        # Crear datos base
        self.stdout.write(self.style.WARNING('📦 Creando datos base...'))
        categorias = self._crear_categorias()
        servicios = self._crear_servicios(categorias)
        paquetes = self._crear_paquetes(servicios)
        usuarios = self._crear_usuarios()
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Datos base creados:\n'
            f'   - {len(categorias)} categorías\n'
            f'   - {len(servicios)} servicios (9 departamentos)\n'
            f'   - {len(paquetes)} paquetes (9 departamentos)\n'
            f'   - {len(usuarios)} usuarios\n'
        ))
        
        # Generar reservas históricas con patrones realistas
        self.stdout.write(self.style.WARNING('🔄 Generando reservas históricas consecutivas (2 años)...'))
        total_reservas = self._generar_reservas_historicas(
            meses, cantidad_por_mes, servicios, paquetes, usuarios
        )
        
        # Calcular estadísticas por departamento (desde servicio/paquete)
        reservas_por_depto = {}
        for reserva in Reserva.objects.all():
            # Obtener departamento desde el servicio o paquete relacionado
            if reserva.servicio:
                depto = reserva.servicio.departamento
            elif reserva.paquete:
                depto = reserva.paquete.departamento
            else:
                depto = 'Sin departamento'
            reservas_por_depto[depto] = reservas_por_depto.get(depto, 0) + 1
        
        self.stdout.write(self.style.SUCCESS(f'\n' + '=' * 80))
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ ¡GENERACIÓN COMPLETADA EXITOSAMENTE!\n\n'
                f'📈 Resumen General:\n'
                f'   - {total_reservas} reservas creadas\n'
                f'   - {len(servicios)} servicios en {len(set([s.departamento for s in servicios]))} departamentos\n'
                f'   - {len(paquetes)} paquetes en {len(set([p.departamento for p in paquetes]))} departamentos\n'
                f'   - {len(usuarios)} clientes registrados\n'
                f'   - Período: {meses} meses ({meses/12:.1f} años)\n\n'
                f'📊 Distribución por Departamento:\n'
            )
        )
        
        # Mostrar distribución por departamento
        for depto, cantidad in sorted(reservas_por_depto.items(), key=lambda x: x[1], reverse=True):
            porcentaje = (cantidad / total_reservas) * 100
            self.stdout.write(f'   - {depto}: {cantidad} reservas ({porcentaje:.1f}%)')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎯 Próximos pasos:\n'
                f'   1. Probar comando de voz: "Ventas de La Paz en enero"\n'
                f'   2. Probar gráficas: POST /api/reportes/graficas/\n'
                f'   3. Probar filtros: "Reservas de Santa Cruz este año"\n'
                f'   4. Exportar reportes en PDF/Excel/DOCX\n'
                f'   5. Verificar multi-moneda (BOB/USD)\n'
            )
        )
        self.stdout.write(self.style.SUCCESS('=' * 80))
    
    def _limpiar_datos(self):
        """Limpia datos de prueba generados previamente."""
        # Eliminar solo usuarios de prueba (cliente_*)
        usuarios_prueba = Usuario.objects.filter(user__username__startswith='cliente_')
        
        # Obtener IDs antes de eliminar
        ids_usuarios = list(usuarios_prueba.values_list('id', flat=True))
        
        # Eliminar reservas de estos usuarios
        Reserva.objects.filter(cliente_id__in=ids_usuarios).delete()
        
        # Eliminar usuarios de prueba y sus users de Django
        for usuario in usuarios_prueba:
            if usuario.user:
                usuario.user.delete()  # Esto eliminará el Usuario por CASCADE
        
        # Eliminar paquetes de prueba
        paquetes_prueba = [
            'Paquete Bolivia Completo', 'Aventura Andina', 'Cultural Express',
            'Naturaleza Extrema', 'Bolivia Express', 'Salar y Lago', 'Salar y Altiplano',
            'Ciudades Coloniales', 'Bolivia Premium', 'Weekend en Bolivia', 
            'Mochilero Bolivia', 'Valle Central', 'Sucre Colonial Premium',
            'Ruta del Vino Tarijeño', 'Misiones Jesuíticas', 'Ruta de la Plata'
        ]
        Paquete.objects.filter(nombre__in=paquetes_prueba).delete()
        
        # Eliminar servicios de prueba (ampliada la lista)
        servicios_prueba = [
            'Salar de Uyuni', 'Lago Titicaca', 'Yungas Adventure',
            'Misiones Tour', 'Trekking Cordillera', 'Valle de la Luna',
            'Isla del Sol', 'Parque Madidi', 'Ciudad de Potosí',
            'Teleférico La Paz', 'Carnaval Oruro', 'Sucre Colonial',
            'Cementerio de Trenes', 'Parque Amboró', 'Samaipata',
            'Valle Sagrado', 'Dinosaurios Park', 'Pampas del Yacuma',
            'Ruta del Vino', 'Valle de la Concepción'
        ]
        Servicio.objects.filter(titulo__in=servicios_prueba).delete()
        
        self.stdout.write('   ✓ Reservas eliminadas')
        self.stdout.write('   ✓ Usuarios de prueba eliminados')
        self.stdout.write('   ✓ Servicios de prueba eliminados')
        self.stdout.write('   ✓ Paquetes de prueba eliminados')
    
    def _crear_categorias(self):
        """Crea categorías de servicios turísticos."""
        categorias_data = [
            "Aventura",
            "Cultural",
            "Naturaleza",
            "Histórico",
            "Gastronómico",
            "Urbano",
        ]
        
        categorias = []
        for nombre in categorias_data:
            cat, _ = Categoria.objects.get_or_create(nombre=nombre)
            categorias.append(cat)
        
        return categorias
    
    def _crear_servicios(self, categorias):
        """Crea servicios turísticos variados PARA TODOS LOS DEPARTAMENTOS DE BOLIVIA."""
        hoy = timezone.now().date()
        
        # Formato: (titulo, desc, precio, capacidad, categoria_idx, departamento, ciudad)
        servicios_data = [
            # ========== LA PAZ (8 servicios) ==========
            ("Yungas Adventure", "Descenso extremo en bicicleta por la ruta de la muerte", 420, 12, 0, 
             "La Paz", "La Paz"),
            ("Lago Titicaca Completo", "Visita a islas flotantes, Copacabana y templos incas", 280, 25, 1,
             "La Paz", "Copacabana"),
            ("Valle de la Luna", "Paisajes lunares únicos y formaciones rocosas", 180, 20, 2,
             "La Paz", "La Paz"),
            ("Teleférico La Paz", "Vista panorámica de la ciudad más alta del mundo", 50, 50, 5,
             "La Paz", "La Paz"),
            ("Isla del Sol", "Tour de un día en el lago sagrado de los incas", 240, 30, 1,
             "La Paz", "Copacabana"),
            ("Tiahuanaco Arqueológico", "Ruinas preincaicas y museo", 200, 35, 3,
             "La Paz", "Tiahuanaco"),
            ("Chacaltaya Trekking", "Caminata en la montaña más alta del mundo", 350, 15, 0,
             "La Paz", "La Paz"),
            ("Mercado de Brujas", "Tour cultural por el mercado tradicional", 80, 40, 1,
             "La Paz", "La Paz"),
            
            # ========== POTOSÍ (6 servicios) ==========
            ("Salar de Uyuni 3D/2N", "Tour de 3 días al salar más grande del mundo", 350, 20, 0,
             "Potosí", "Uyuni"),
            ("Ciudad de Potosí Colonial", "Minas coloniales, Cerro Rico y museo de la moneda", 220, 22, 3,
             "Potosí", "Potosí"),
            ("Cementerio de Trenes", "Visita al cementerio de trenes histórico", 80, 30, 3,
             "Potosí", "Uyuni"),
            ("Lagunas de Colores", "Tour a lagunas colorada, verde y blanca", 450, 18, 2,
             "Potosí", "Uyuni"),
            ("Termas de Polques", "Aguas termales en el altiplano", 180, 25, 2,
             "Potosí", "Uyuni"),
            ("Casa de la Moneda", "Museo histórico colonial", 120, 40, 3,
             "Potosí", "Potosí"),
            
            # ========== SANTA CRUZ (8 servicios) ==========
            ("Parque Amboró Expedición", "Expedición al parque nacional de biodiversidad", 450, 15, 2,
             "Santa Cruz", "Santa Cruz de la Sierra"),
            ("Samaipata El Fuerte", "Fuerte precolombino patrimonio UNESCO", 200, 25, 1,
             "Santa Cruz", "Samaipata"),
            ("Misiones Jesuíticas Tour", "Recorrido por 6 misiones barrocas", 310, 18, 1,
             "Santa Cruz", "San José de Chiquitos"),
            ("Biocentro Güembé", "Complejo turístico con mariposario", 150, 50, 2,
             "Santa Cruz", "Santa Cruz de la Sierra"),
            ("Parque Lomas de Arena", "Dunas en plena selva tropical", 120, 30, 2,
             "Santa Cruz", "Santa Cruz de la Sierra"),
            ("Nevado Huayna Potosí", "Ascenso de alta montaña", 580, 10, 0,
             "Santa Cruz", "Santa Cruz de la Sierra"),
            ("Vallegrande Che Guevara", "Ruta histórica del Che", 250, 20, 3,
             "Santa Cruz", "Vallegrande"),
            ("Noel Kempff Mercado", "Parque nacional patrimonio natural", 650, 12, 2,
             "Santa Cruz", "San Ignacio de Velasco"),
            
            # ========== COCHABAMBA (6 servicios) ==========
            ("Trekking Cordillera Tunari", "Caminata de alta montaña", 500, 15, 0,
             "Cochabamba", "Cochabamba"),
            ("Valle Sagrado Cochabamba", "Tour por el valle fértil y pueblos", 190, 20, 2,
             "Cochabamba", "Cochabamba"),
            ("Cristo de la Concordia", "Visita al Cristo más alto de América", 60, 45, 5,
             "Cochabamba", "Cochabamba"),
            ("Incallajta Ruinas", "Fortaleza inca mejor conservada", 280, 18, 3,
             "Cochabamba", "Pocona"),
            ("Torotoro National Park", "Dinosaurios, cavernas y cañones", 420, 20, 2,
             "Cochabamba", "Torotoro"),
            ("Laguna Alalay", "Paseo ecológico y observación de aves", 80, 35, 2,
             "Cochabamba", "Cochabamba"),
            
            # ========== CHUQUISACA (5 servicios) ==========
            ("Sucre Colonial Premium", "City tour por la capital histórica", 150, 30, 1,
             "Chuquisaca", "Sucre"),
            ("Dinosaurios Park Cal Orck'o", "Visita al parque de huellas de dinosaurios", 120, 40, 3,
             "Chuquisaca", "Sucre"),
            ("Tarabuco Mercado Indígena", "Experiencia cultural en mercado dominical", 180, 25, 1,
             "Chuquisaca", "Tarabuco"),
            ("Cañón de Pilcomayo", "Trekking y rappel en cañones", 380, 15, 0,
             "Chuquisaca", "Sucre"),
            ("Maragua Cráter", "Caminata al cráter y comunidades", 250, 20, 2,
             "Chuquisaca", "Maragua"),
            
            # ========== ORURO (4 servicios) ==========
            ("Carnaval de Oruro", "Experiencia del carnaval más grande de Bolivia", 800, 100, 3,
             "Oruro", "Oruro"),
            ("Santuario de la Virgen del Socavón", "Tour religioso y museo folclórico", 100, 50, 3,
             "Oruro", "Oruro"),
            ("Salar de Coipasa", "Salar gemelo del de Uyuni", 320, 18, 2,
             "Oruro", "Oruro"),
            ("Lago Poopó", "Observación de flamencos", 150, 25, 2,
             "Oruro", "Oruro"),
            
            # ========== BENI (5 servicios) ==========
            ("Parque Madidi Expedición", "Expedición a la selva amazónica", 650, 10, 2,
             "Beni", "Rurrenabaque"),
            ("Pampas del Yacuma Safari", "Safari fotográfico en las pampas", 550, 12, 2,
             "Beni", "Rurrenabaque"),
            ("Río Yacuma Navegación", "Tour en bote por el río", 380, 20, 2,
             "Beni", "Santa Rosa"),
            ("Trinidad Colonial", "City tour por la capital beniana", 120, 30, 5,
             "Beni", "Trinidad"),
            ("Laguna Rogaguado", "Pesca deportiva y observación fauna", 420, 15, 2,
             "Beni", "Trinidad"),
            
            # ========== TARIJA (6 servicios) ==========
            ("Ruta del Vino Premium", "Tour por viñedos tarijeños con cata", 280, 20, 4,
             "Tarija", "Tarija"),
            ("Valle de la Concepción", "Degustación de vinos y paisajes", 320, 18, 4,
             "Tarija", "Tarija"),
            ("Reserva Biológica Sama", "Trekking en alta montaña y lagunas", 380, 15, 2,
             "Tarija", "Tarija"),
            ("Tariquia National Park", "Bosque nublado y biodiversidad", 450, 12, 2,
             "Tarija", "Tarija"),
            ("Padcaya Ruta Histórica", "Tour por pueblo colonial", 150, 25, 1,
             "Tarija", "Padcaya"),
            ("Gastronomía Tarijeña", "Tour gastronómico por restaurantes típicos", 200, 20, 4,
             "Tarija", "Tarija"),
            
            # ========== PANDO (4 servicios) ==========
            ("Amazonía Pandina", "Expedición a la selva virgen", 720, 8, 2,
             "Pando", "Cobija"),
            ("Lago Bay", "Pesca y observación de fauna", 380, 15, 2,
             "Pando", "Cobija"),
            ("Manuripi Heath", "Reserva de biodiversidad", 550, 10, 2,
             "Pando", "Cobija"),
            ("Comunidades Indígenas", "Turismo comunitario", 420, 12, 1,
             "Pando", "Cobija"),
        ]
        
        servicios = []
        for titulo, desc, precio, capacidad, cat_idx, depto, ciudad in servicios_data:
            servicio, created = Servicio.objects.get_or_create(
                titulo=titulo,
                defaults={
                    'descripcion': desc,
                    'duracion': f'{random.randint(1, 5)} días',
                    'capacidad_max': capacidad,
                    'punto_encuentro': 'Plaza Principal / Hotel',
                    'estado': 'Activo',
                    'categoria': categorias[cat_idx],
                    'precio_usd': Decimal(str(precio)),
                    'imagen_url': f'https://picsum.photos/seed/{titulo}/800/600',
                    'departamento': depto,
                    'ciudad': ciudad
                }
            )
            
            # Actualizar servicios existentes con los nuevos campos
            if not created:
                servicio.departamento = depto
                servicio.ciudad = ciudad
                servicio.save()
            
            servicios.append(servicio)
        
        return servicios
    
    def _crear_paquetes(self, servicios):
        """Crea paquetes turísticos combinados PARA TODOS LOS DEPARTAMENTOS."""
        hoy = timezone.now().date()
        
        # Formato: (nombre, desc, precio, dias, destacado, departamento, ciudad, tipo_destino)
        paquetes_data = [
            # ========== LA PAZ (5 paquetes) ==========
            ("Aventura Andina Completa", "Paquete de aventura extrema en La Paz", 850, 5, True,
             "La Paz", "La Paz", "Aventura"),
            ("Cultural Express La Paz", "Lo mejor de la cultura paceña", 600, 3, True,
             "La Paz", "La Paz", "Cultural"),
            ("Bolivia Express", "Recorrido rápido por lo esencial", 450, 2, True,
             "La Paz", "La Paz", "Cultural"),
            ("Lago Titicaca Premium", "Experiencia completa en el lago sagrado", 980, 4, True,
             "La Paz", "Copacabana", "Cultural"),
            ("Yungas y Valles", "Aventura en yungas y valles", 720, 4, True,
             "La Paz", "La Paz", "Aventura"),
            
            # ========== SANTA CRUZ (4 paquetes) ==========
            ("Naturaleza Extrema", "Expedición por parques nacionales", 1500, 10, True,
             "Santa Cruz", "Santa Cruz de la Sierra", "Natural"),
            ("Misiones Jesuíticas Completo", "Tour completo por las misiones", 980, 6, True,
             "Santa Cruz", "Santa Cruz de la Sierra", "Cultural"),
            ("Santa Cruz Express", "Lo mejor de Santa Cruz en 3 días", 650, 3, True,
             "Santa Cruz", "Santa Cruz de la Sierra", "Cultural"),
            ("Parques y Selva", "Amboró y Noel Kempff", 1800, 8, True,
             "Santa Cruz", "Santa Cruz de la Sierra", "Natural"),
            
            # ========== POTOSÍ (4 paquetes) ==========
            ("Salar y Altiplano Premium", "Experiencia completa Uyuni + lagunas", 1280, 7, True,
             "Potosí", "Uyuni", "Natural"),
            ("Ruta de la Plata", "Historia minera de Potosí", 540, 3, True,
             "Potosí", "Potosí", "Cultural"),
            ("Uyuni Express 3D/2N", "Salar de Uyuni en 3 días", 780, 3, True,
             "Potosí", "Uyuni", "Natural"),
            ("Potosí Colonial", "Ciudad imperial y Cerro Rico", 420, 2, True,
             "Potosí", "Potosí", "Cultural"),
            
            # ========== COCHABAMBA (3 paquetes) ==========
            ("Valle Central Premium", "Naturaleza y gastronomía cochabambina", 720, 4, True,
             "Cochabamba", "Cochabamba", "Rural"),
            ("Trekking Tunari", "Alta montaña en la cordillera", 850, 5, True,
             "Cochabamba", "Cochabamba", "Aventura"),
            ("Torotoro Adventure", "Dinosaurios, cavernas y cañones", 920, 5, True,
             "Cochabamba", "Torotoro", "Natural"),
            
            # ========== CHUQUISACA (3 paquetes) ==========
            ("Sucre Colonial Premium", "Experiencia colonial de lujo", 890, 4, True,
             "Chuquisaca", "Sucre", "Cultural"),
            ("Chuquisaca Completo", "Sucre, Tarabuco y Maragua", 1050, 6, True,
             "Chuquisaca", "Sucre", "Cultural"),
            ("Weekend Sucre", "Fin de semana en la ciudad blanca", 480, 2, True,
             "Chuquisaca", "Sucre", "Cultural"),
            
            # ========== TARIJA (3 paquetes) ==========
            ("Ruta del Vino Tarijeño", "Tour enológico completo", 1150, 5, True,
             "Tarija", "Tarija", "Rural"),
            ("Weekend en Tarija", "Vinos y gastronomía en fin de semana", 580, 2, True,
             "Tarija", "Tarija", "Rural"),
            ("Tarija Natural", "Sama y Tariquia", 950, 5, True,
             "Tarija", "Tarija", "Natural"),
            
            # ========== ORURO (2 paquetes) ==========
            ("Carnaval de Oruro", "Experiencia completa del carnaval", 1200, 4, True,
             "Oruro", "Oruro", "Cultural"),
            ("Oruro Express", "Santuario y cultura", 380, 2, True,
             "Oruro", "Oruro", "Cultural"),
            
            # ========== BENI (3 paquetes) ==========
            ("Amazonía Beniana", "Madidi y Pampas del Yacuma", 1680, 8, True,
             "Beni", "Rurrenabaque", "Natural"),
            ("Pampas Adventure", "Safari fotográfico en las pampas", 980, 5, True,
             "Beni", "Rurrenabaque", "Natural"),
            ("Selva Express", "Experiencia amazónica rápida", 720, 3, True,
             "Beni", "Rurrenabaque", "Natural"),
            
            # ========== PANDO (2 paquetes) ==========
            ("Amazonía Pandina", "Selva virgen de Pando", 1450, 7, True,
             "Pando", "Cobija", "Natural"),
            ("Pando Explorer", "Aventura en la frontera", 880, 4, True,
             "Pando", "Cobija", "Natural"),
            
            # ========== MULTI-DEPARTAMENTAL (5 paquetes) ==========
            ("Bolivia Completo Premium", "Tour completo por Bolivia", 2800, 14, True,
             "Multi-departamental", "Varias ciudades", "Cultural"),
            ("Bolivia Premium 21 Días", "Experiencia de lujo extendida", 4500, 21, True,
             "Multi-departamental", "Varias ciudades", "Cultural"),
            ("Mochilero Bolivia", "Paquete económico para viajeros", 920, 10, True,
             "Multi-departamental", "Varias ciudades", "Aventura"),
            ("Ruta Altiplánica", "La Paz, Oruro, Potosí", 1450, 8, True,
             "Multi-departamental", "Varias ciudades", "Cultural"),
            ("Oriente Boliviano", "Santa Cruz, Beni, Pando", 1950, 10, True,
             "Multi-departamental", "Varias ciudades", "Natural"),
        ]
        
        paquetes = []
        for nombre, desc, precio, dias, destacado, depto, ciudad, tipo_dest in paquetes_data:
            paquete, created = Paquete.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': desc,
                    'duracion': f'{dias} días',
                    'precio_base': Decimal(str(precio)),
                    'cupos_disponibles': random.randint(20, 50),
                    'cupos_ocupados': 0,
                    'fecha_inicio': hoy - timedelta(days=730),  # 2 años atrás
                    'fecha_fin': hoy + timedelta(days=365),  # 1 año adelante
                    'estado': 'Activo',
                    'punto_salida': 'Terminal de buses / Aeropuerto',
                    'destacado': destacado and random.random() > 0.5,
                    'imagen_principal': f'https://picsum.photos/seed/{nombre}/1200/800',
                    'es_personalizado': False,
                    'departamento': depto,
                    'ciudad': ciudad,
                    'tipo_destino': tipo_dest
                }
            )
            
            # Actualizar paquetes existentes con los nuevos campos
            if not created:
                paquete.departamento = depto
                paquete.ciudad = ciudad
                paquete.tipo_destino = tipo_dest
                paquete.fecha_inicio = hoy - timedelta(days=730)
                paquete.save()
            
            paquetes.append(paquete)
        
        return paquetes
    
    def _crear_usuarios(self):
        """Crea usuarios de prueba con perfiles variados."""
        nombres = [
            "Juan Pérez", "María García", "Carlos López", "Ana Martínez", 
            "Pedro Rodríguez", "Laura Fernández", "Diego Sánchez", "Sofía Torres",
            "Luis Ramírez", "Carmen Flores", "Miguel Ángel Cruz", "Valentina Ruiz",
            "Fernando Castro", "Isabella Morales", "Roberto Gutiérrez", "Camila Reyes",
            "Jorge Herrera", "Lucía Mendoza", "Andrés Silva", "Victoria Vega",
            "Gabriel Ortiz", "Daniela Romero", "Ricardo Vargas", "Natalia Jiménez",
            "Sebastián Molina", "Paula Castillo", "Martín Núñez", "Andrea Muñoz",
        ]
        
        paises = ["Bolivia", "Argentina", "Perú", "Chile", "Brasil", "Colombia", "España", "México"]
        
        usuarios = []
        for i, nombre in enumerate(nombres):
            username = f"cliente_{i+1:03d}"
            email = f"{username}@example.com"
            
            # Crear o obtener user de Django
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email, 
                    'first_name': nombre.split()[0],
                    'last_name': nombre.split()[-1]
                }
            )
            
            # Crear perfil Usuario
            usuario, created = Usuario.objects.get_or_create(
                user=user,
                defaults={
                    'nombre': nombre,
                    'telefono': f'+591 7{random.randint(1000000, 9999999)}',
                    'num_viajes': random.randint(0, 15),
                    'pais': random.choice(paises),
                    'genero': random.choice(['M', 'F']),
                }
            )
            usuarios.append(usuario)
        
        return usuarios
    
    def _generar_reservas_historicas(self, meses, cantidad_por_mes, servicios, paquetes, usuarios):
        """
        Genera reservas históricas con patrones realistas CONSECUTIVOS.
        Distribución uniforme en 2 años completos con picos en temporadas altas.
        """
        total_reservas = 0
        estados_reserva = ['PENDIENTE', 'CONFIRMADA', 'PAGADA', 'COMPLETADA', 'CANCELADA']
        metodos_pago = ['Tarjeta', 'Transferencia', 'Efectivo']
        
        hoy = timezone.now().date()
        fecha_inicio = hoy - timedelta(days=30 * meses)
        
        # Temporadas altas (más reservas): verano, fiestas patrias, carnaval
        # Enero-Febrero: verano (1.5x)
        # Junio-Agosto: invierno/vacaciones (1.4x)
        # Diciembre: navidad/año nuevo (1.6x)
        temporadas = {
            1: 1.5, 2: 1.5, 3: 1.0, 4: 0.9, 5: 0.9, 6: 1.4,
            7: 1.4, 8: 1.4, 9: 1.0, 10: 1.1, 11: 1.2, 12: 1.6
        }
        
        self.stdout.write(self.style.WARNING('\n🗓️  Generando reservas MES POR MES (consecutivo):'))
        
        # Generar reservas consecutivas mes por mes
        for mes_idx in range(meses - 1, -1, -1):  # De más antiguo a más reciente
            fecha_mes = hoy - timedelta(days=30 * mes_idx)
            mes_numero = fecha_mes.month
            año = fecha_mes.year
            
            # Calcular días del mes
            if mes_numero == 12:
                siguiente_mes = fecha_mes.replace(day=1, month=1, year=año + 1)
            else:
                siguiente_mes = fecha_mes.replace(day=1, month=mes_numero + 1)
            
            dias_en_mes = (siguiente_mes - fecha_mes.replace(day=1)).days
            
            # Ajustar cantidad según temporada
            multiplicador = temporadas.get(mes_numero, 1.0)
            cantidad_mes = int(cantidad_por_mes * multiplicador)
            
            # Generar reservas distribuidas uniformemente en el mes
            for i in range(cantidad_mes):
                # Distribución uniforme de días en el mes
                dia = int((i / cantidad_mes) * dias_en_mes) + 1
                dia = min(dia, dias_en_mes)  # Asegurar que no exceda los días del mes
                
                try:
                    fecha_reserva = fecha_mes.replace(day=dia)
                except ValueError:
                    fecha_reserva = fecha_mes.replace(day=min(dia, 28))
                
                # Decidir si es reserva de servicio o paquete (65% paquetes, 35% servicios)
                es_paquete = random.random() < 0.65
                usuario = random.choice(usuarios)
                
                if es_paquete:
                    paquete = random.choice(paquetes)
                    # Variación de precio ±12%
                    variacion = Decimal(str(random.uniform(0.88, 1.12)))
                    total = paquete.precio_base * variacion
                    servicio = None
                    # Heredar departamento del paquete
                    departamento = paquete.departamento
                    ciudad = paquete.ciudad
                    tipo_destino = paquete.tipo_destino
                else:
                    servicio = random.choice(servicios)
                    paquete = None
                    # Variación de precio ±15%
                    variacion = Decimal(str(random.uniform(0.85, 1.15)))
                    total = servicio.precio_usd * variacion
                    # Heredar departamento del servicio
                    departamento = servicio.departamento
                    ciudad = servicio.ciudad
                    # Paquetes tienen tipo_destino, servicios no - usar valor por defecto
                    tipo_destino = 'Cultural'
                
                # Convertir a BOB (1 USD = 6.96 BOB)
                total_bob = (total * Decimal('6.96')).quantize(Decimal('0.01'))
                
                # Estado de la reserva según antigüedad
                meses_antiguedad = mes_idx
                if meses_antiguedad > 18:  # Muy antiguas (>18 meses)
                    estado = random.choices(
                        estados_reserva, 
                        weights=[2, 5, 25, 60, 8]  # 60% completadas
                    )[0]
                elif meses_antiguedad > 6:  # Antiguas (6-18 meses)
                    estado = random.choices(
                        estados_reserva, 
                        weights=[3, 10, 30, 50, 7]  # 50% completadas
                    )[0]
                elif meses_antiguedad > 2:  # Medias (2-6 meses)
                    estado = random.choices(
                        estados_reserva, 
                        weights=[8, 20, 35, 28, 9]
                    )[0]
                else:  # Recientes (<2 meses)
                    estado = random.choices(
                        estados_reserva, 
                        weights=[20, 30, 30, 12, 8]
                    )[0]
                
                # Crear reserva
                reserva = Reserva.objects.create(
                    fecha=fecha_reserva,
                    fecha_inicio=timezone.make_aware(
                        datetime.combine(
                            fecha_reserva + timedelta(days=random.randint(3, 45)), 
                            datetime.min.time()
                        )
                    ),
                    estado=estado,
                    total=total_bob,
                    moneda='BOB',
                    cliente=usuario,
                    servicio=servicio,
                    paquete=paquete
                )
                
                # Crear pago si está pagada o completada
                if estado in ['PAGADA', 'COMPLETADA']:
                    metodo = random.choices(
                        metodos_pago,
                        weights=[65, 28, 7]  # 65% tarjeta, 28% transferencia, 7% efectivo
                    )[0]
                    
                    Pago.objects.create(
                        monto=total_bob,
                        metodo=metodo,
                        fecha_pago=fecha_reserva + timedelta(days=random.randint(0, 3)),
                        estado='Confirmado',
                        reserva=reserva,
                        url_stripe=f'https://stripe.com/payment/{random.randint(100000, 999999)}' if metodo == 'Tarjeta' else None
                    )
                
                # Crear visitantes aleatorios (1-4 personas)
                num_visitantes = random.randint(1, 4)
                nombres_visitantes = ["Juan", "María", "Pedro", "Ana", "Luis", "Carmen", "Carlos", "Sofía", "Miguel", "Laura"]
                apellidos = ["García", "López", "Martínez", "Pérez", "Rodríguez", "González", "Fernández", "Sánchez", "Torres", "Ramírez"]
                nacionalidades = ["Bolivia", "Argentina", "Perú", "Chile", "Brasil", "Colombia", "España", "México", "USA", "Francia"]
                
                for v in range(num_visitantes):
                    visitante = Visitante.objects.create(
                        nombre=random.choice(nombres_visitantes),
                        apellido=random.choice(apellidos),
                        fecha_nac=timezone.now().date() - timedelta(days=random.randint(7300, 25550)),  # 20-70 años
                        nacionalidad=random.choice(nacionalidades),
                        nro_doc=f"CI-{random.randint(1000000, 9999999)}",
                        es_titular=(v == 0)
                    )
                    ReservaVisitante.objects.create(reserva=reserva, visitante=visitante)
                
                total_reservas += 1
            
            # Mostrar progreso por mes
            mes_nombre = [
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
            ][mes_numero - 1]
            
            self.stdout.write(
                f'   ✓ {mes_nombre} {año}: {cantidad_mes} reservas | '
                f'Total acumulado: {total_reservas}'
            )
        
        return total_reservas
