"""
Sistema de reportes avanzados con soporte para filtros dinámicos y comandos de voz.
CU19 - Reportes avanzados (estáticos y dinámicos) y por voz
"""
from django.db.models import Sum, Count, Avg, Q, F, Max
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union
import re

from .models import Reserva, Pago, Usuario, Servicio, Paquete, Visitante


class InterpretadorComandosVoz:
    """
    Interpreta comandos de voz (texto) y extrae filtros para reportes.
    Ejemplo: "quiero un reporte desde el 1/1/2025 hasta el 30/1/2025 solo con los clientes que compraron paquetes mayores a 1000 bs"
    """
    
    @staticmethod
    def parsear_fecha(texto: str) -> Optional[datetime]:
        """Extrae y convierte fechas en diferentes formatos."""
        # Formatos comunes: 1/1/2025, 01-01-2025, 1 de enero de 2025
        patrones = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # 1/1/2025 o 1-1-2025
            r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',  # 1 de enero de 2025
        ]
        
        meses_texto = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    if '/' in patron or '-' in patron:
                        dia, mes, año = match.groups()
                        return datetime(int(año), int(mes), int(dia))
                    else:
                        dia, mes_nombre, año = match.groups()
                        mes = meses_texto.get(mes_nombre.lower())
                        if mes:
                            return datetime(int(año), mes, int(dia))
                except (ValueError, TypeError):
                    continue
        return None
    
    @staticmethod
    def extraer_rango_fechas(texto: str) -> tuple:
        """Extrae fecha_inicio y fecha_fin del comando con soporte para fechas relativas."""
        fecha_inicio = None
        fecha_fin = None
        texto_lower = texto.lower()
        hoy = timezone.now().date()
        
        # HOY
        if 'hoy' in texto_lower:
            return datetime.combine(hoy, datetime.min.time()), datetime.combine(hoy, datetime.max.time())
        
        # AYER
        if 'ayer' in texto_lower:
            ayer = hoy - timedelta(days=1)
            return datetime.combine(ayer, datetime.min.time()), datetime.combine(ayer, datetime.max.time())
        
        # ÚLTIMOS N DÍAS
        match_ultimos_dias = re.search(r'últimos?\s+(\d+)\s+días?', texto_lower)
        if match_ultimos_dias:
            dias = int(match_ultimos_dias.group(1))
            fecha_inicio = datetime.combine(hoy - timedelta(days=dias), datetime.min.time())
            fecha_fin = datetime.combine(hoy, datetime.max.time())
            return fecha_inicio, fecha_fin
        
        # ESTA SEMANA (lunes a hoy)
        if re.search(r'esta\s+semana', texto_lower):
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            return datetime.combine(inicio_semana, datetime.min.time()), datetime.combine(hoy, datetime.max.time())
        
        # SEMANA PASADA / ÚLTIMA SEMANA
        if re.search(r'(semana\s+pasada|última\s+semana|semana\s+anterior)', texto_lower):
            fin_semana_pasada = hoy - timedelta(days=hoy.weekday() + 1)
            inicio_semana_pasada = fin_semana_pasada - timedelta(days=6)
            return datetime.combine(inicio_semana_pasada, datetime.min.time()), datetime.combine(fin_semana_pasada, datetime.max.time())
        
        # ESTE MES (primer día del mes a hoy)
        if re.search(r'este\s+mes', texto_lower):
            inicio_mes = hoy.replace(day=1)
            return datetime.combine(inicio_mes, datetime.min.time()), datetime.combine(hoy, datetime.max.time())
        
        # MES PASADO / ÚLTIMO MES / MES ANTERIOR
        if re.search(r'(mes\s+pasado|último\s+mes|mes\s+anterior)', texto_lower):
            primer_dia_mes_actual = hoy.replace(day=1)
            ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
            primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
            return datetime.combine(primer_dia_mes_pasado, datetime.min.time()), datetime.combine(ultimo_dia_mes_pasado, datetime.max.time())
        
        # ESTE AÑO
        if re.search(r'este\s+año', texto_lower):
            inicio_año = hoy.replace(month=1, day=1)
            return datetime.combine(inicio_año, datetime.min.time()), datetime.combine(hoy, datetime.max.time())
        
        # AÑO PASADO / ÚLTIMO AÑO
        if re.search(r'(año\s+pasado|último\s+año)', texto_lower):
            año_pasado = hoy.year - 1
            inicio_año_pasado = hoy.replace(year=año_pasado, month=1, day=1)
            fin_año_pasado = hoy.replace(year=año_pasado, month=12, day=31)
            return datetime.combine(inicio_año_pasado, datetime.min.time()), datetime.combine(fin_año_pasado, datetime.max.time())
        
        # Buscar "desde ... hasta ..."
        match_rango = re.search(
            r'desde\s+(.+?)\s+hasta\s+(.+?)(?:\s+|$)',
            texto,
            re.IGNORECASE
        )
        
        if match_rango:
            fecha_inicio_texto, fecha_fin_texto = match_rango.groups()
            fecha_inicio = InterpretadorComandosVoz.parsear_fecha(fecha_inicio_texto)
            fecha_fin = InterpretadorComandosVoz.parsear_fecha(fecha_fin_texto)
        
        # Si no hay rango explícito, buscar fechas individuales
        if not fecha_inicio:
            fechas = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', texto)
            if len(fechas) >= 2:
                fecha_inicio = InterpretadorComandosVoz.parsear_fecha(fechas[0])
                fecha_fin = InterpretadorComandosVoz.parsear_fecha(fechas[1])
            elif len(fechas) == 1:
                fecha_inicio = InterpretadorComandosVoz.parsear_fecha(fechas[0])
                fecha_fin = timezone.now()
        
        return fecha_inicio, fecha_fin
    
    @staticmethod
    def extraer_monto_minimo(texto: str) -> Optional[Decimal]:
        """Extrae monto mínimo del comando."""
        # Buscar "mayores a 1000", "más de 1000", "superiores a 1000"
        patrones = [
            r'mayor(?:es)?\s+(?:a|que)\s+(\d+)',
            r'm[áa]s\s+de\s+(\d+)',
            r'superior(?:es)?\s+a\s+(\d+)',
            r'sobre\s+(\d+)',
        ]
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1))
                except (ValueError, TypeError):
                    continue
        return None
    
    @staticmethod
    def extraer_monto_maximo(texto: str) -> Optional[Decimal]:
        """Extrae monto máximo del comando."""
        # Buscar "menores a 500", "menos de 500", "inferiores a 500"
        patrones = [
            r'menor(?:es)?\s+(?:a|que)\s+(\d+)',
            r'menos\s+de\s+(\d+)',
            r'inferior(?:es)?\s+a\s+(\d+)',
            r'bajo\s+(\d+)',
        ]
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1))
                except (ValueError, TypeError):
                    continue
        return None
    
    @staticmethod
    def extraer_tipo_producto(texto: str) -> Optional[str]:
        """Identifica si se buscan paquetes, servicios o ambos."""
        texto_lower = texto.lower()
        
        if 'paquete' in texto_lower and 'servicio' not in texto_lower:
            return 'paquete'
        elif 'servicio' in texto_lower and 'paquete' not in texto_lower:
            return 'servicio'
        return None  # Ambos
    
    @staticmethod
    def extraer_estado(texto: str) -> Optional[str]:
        """Extrae estado de reserva si se menciona."""
        texto_lower = texto.lower()
        
        estados_map = {
            'pendiente': 'PENDIENTE',
            'confirmada': 'CONFIRMADA',
            'pagada': 'PAGADA',
            'completada': 'COMPLETADA',
            'cancelada': 'CANCELADA',
        }
        
        for clave, valor in estados_map.items():
            if clave in texto_lower:
                return valor
        return None
    
    @staticmethod
    def extraer_limite(texto: str) -> Optional[int]:
        """Extrae límite de resultados del comando."""
        # Buscar "top N", "primeros N", "mejores N", "últimos N"
        patrones = [
            r'top\s+(\d+)',
            r'primeros?\s+(\d+)',
            r'mejores\s+(\d+)',
            r'últimos?\s+(\d+)',
            r'solo\s+(\d+)',
            r'máximo\s+(\d+)',
        ]
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None
    
    @staticmethod
    def extraer_formato(texto: str) -> str:
        """Detecta formato deseado del reporte."""
        texto_lower = texto.lower()
        
        if any(word in texto_lower for word in ['pdf', 'en pdf', 'formato pdf']):
            return 'pdf'
        if any(word in texto_lower for word in ['excel', 'xlsx', 'en excel', 'formato excel', 'hoja de cálculo']):
            return 'excel'
        
        return 'json'
    
    @classmethod
    def interpretar(cls, comando_voz: str) -> Dict[str, Any]:
        """
        Interpreta un comando de voz y devuelve un diccionario con filtros.
        
        Ejemplo:
        >>> InterpretadorComandosVoz.interpretar(
        ...     "quiero un reporte desde el 1/1/2025 hasta el 30/1/2025 "
        ...     "solo con los clientes que compraron paquetes mayores a 1000 bs"
        ... )
        {
            'fecha_inicio': datetime(2025, 1, 1),
            'fecha_fin': datetime(2025, 1, 30),
            'monto_minimo': Decimal('1000'),
            'tipo_producto': 'paquete',
            'comando_original': '...'
        }
        """
        filtros: Dict[str, Union[str, datetime, Decimal, int]] = {'comando_original': comando_voz}
        
        # Extraer rango de fechas
        fecha_inicio, fecha_fin = cls.extraer_rango_fechas(comando_voz)
        if fecha_inicio:
            filtros['fecha_inicio'] = fecha_inicio
        if fecha_fin:
            filtros['fecha_fin'] = fecha_fin
        
        # Extraer montos
        monto_min = cls.extraer_monto_minimo(comando_voz)
        if monto_min:
            filtros['monto_minimo'] = monto_min  # type: ignore
        
        monto_max = cls.extraer_monto_maximo(comando_voz)
        if monto_max:
            filtros['monto_maximo'] = monto_max  # type: ignore
        
        # Extraer tipo de producto
        tipo = cls.extraer_tipo_producto(comando_voz)
        if tipo:
            filtros['tipo_producto'] = tipo
        
        # Extraer estado
        estado = cls.extraer_estado(comando_voz)
        if estado:
            filtros['estado'] = estado
        
        # Extraer límite
        limite = cls.extraer_limite(comando_voz)
        if limite:
            filtros['limite'] = limite
        
        # Extraer formato
        formato = cls.extraer_formato(comando_voz)
        filtros['formato'] = formato
        
        return filtros


class GeneradorReportes:
    """
    Genera reportes avanzados basados en filtros dinámicos.
    """
    
    @staticmethod
    def aplicar_filtros(queryset, filtros: Dict[str, Any]):
        """Aplica filtros dinámicos a un queryset de Reserva."""
        q_filters = Q()
        
        # ============ FILTROS TEMPORALES ============
        # Filtro por rango de fechas
        if 'fecha_inicio' in filtros:
            q_filters &= Q(fecha__gte=filtros['fecha_inicio'])
        if 'fecha_fin' in filtros:
            q_filters &= Q(fecha__lte=filtros['fecha_fin'])
        
        # Filtro por día de semana vs fin de semana
        if 'solo_fines_semana' in filtros and filtros['solo_fines_semana']:
            q_filters &= Q(fecha__week_day__in=[1, 7])  # Domingo=1, Sábado=7
        if 'solo_dias_semana' in filtros and filtros['solo_dias_semana']:
            q_filters &= Q(fecha__week_day__in=[2, 3, 4, 5, 6])  # Lunes-Viernes
        
        # Filtro por mes específico
        if 'mes' in filtros:
            q_filters &= Q(fecha__month=filtros['mes'])
        if 'año' in filtros:
            q_filters &= Q(fecha__year=filtros['año'])
        
        # Filtro por trimestre
        if 'trimestre' in filtros:
            trimestre = filtros['trimestre']
            meses = {
                1: [1, 2, 3],
                2: [4, 5, 6],
                3: [7, 8, 9],
                4: [10, 11, 12]
            }
            if trimestre in meses:
                q_filters &= Q(fecha__month__in=meses[trimestre])
        
        # ============ FILTROS DE MONTO ============
        if 'monto_minimo' in filtros:
            q_filters &= Q(total__gte=filtros['monto_minimo'])
        if 'monto_maximo' in filtros:
            q_filters &= Q(total__lte=filtros['monto_maximo'])
        
        # ============ FILTROS DE PRODUCTO ============
        # Filtro por tipo de producto
        if 'tipo_producto' in filtros:
            if filtros['tipo_producto'] == 'paquete':
                q_filters &= Q(paquete__isnull=False)
            elif filtros['tipo_producto'] == 'servicio':
                q_filters &= Q(servicio__isnull=False)
        
        # Filtro por departamento (NUEVO)
        if 'departamento' in filtros:
            dept = filtros['departamento']
            q_filters &= (Q(paquete__departamento=dept) | Q(servicio__departamento=dept))
        
        # Filtro por ciudad (NUEVO)
        if 'ciudad' in filtros:
            ciudad = filtros['ciudad']
            q_filters &= (Q(paquete__ciudad__icontains=ciudad) | Q(servicio__ciudad__icontains=ciudad))
        
        # Filtro por tipo de destino (NUEVO)
        if 'tipo_destino' in filtros:
            q_filters &= Q(paquete__tipo_destino=filtros['tipo_destino'])
        
        # Filtro por categoría
        if 'categoria' in filtros:
            q_filters &= Q(servicio__categoria__nombre=filtros['categoria'])
        
        # Filtro por paquetes destacados
        if 'solo_destacados' in filtros and filtros['solo_destacados']:
            q_filters &= Q(paquete__destacado=True)
        
        # Filtro por paquetes personalizados
        if 'solo_personalizados' in filtros and filtros['solo_personalizados']:
            q_filters &= Q(paquete__es_personalizado=True)
        
        # Filtro por duración
        if 'duracion_dias' in filtros:
            q_filters &= (Q(paquete__duracion__icontains=f"{filtros['duracion_dias']} día") | 
                         Q(servicio__duracion__icontains=f"{filtros['duracion_dias']} día"))
        
        # ============ FILTROS DE ESTADO ============
        # Filtro por estado
        if 'estado' in filtros:
            q_filters &= Q(estado=filtros['estado'])
        
        # Filtro por estados múltiples
        if 'estados' in filtros and isinstance(filtros['estados'], list):
            q_filters &= Q(estado__in=filtros['estados'])
        
        # ============ FILTROS DE CLIENTE ============
        # Filtro por cliente específico
        if 'cliente_id' in filtros:
            q_filters &= Q(cliente_id=filtros['cliente_id'])
        
        # Filtro por tipo de cliente (NUEVO - basado en cantidad de reservas)
        if 'tipo_cliente' in filtros:
            if filtros['tipo_cliente'] == 'nuevo':
                # Clientes con 1-2 reservas
                clientes_nuevos = Usuario.objects.annotate(
                    num_reservas=Count('reservas')
                ).filter(num_reservas__lte=2).values_list('id', flat=True)
                q_filters &= Q(cliente_id__in=clientes_nuevos)
            elif filtros['tipo_cliente'] == 'recurrente':
                # Clientes con 3-5 reservas
                clientes_recurrentes = Usuario.objects.annotate(
                    num_reservas=Count('reservas')
                ).filter(num_reservas__gte=3, num_reservas__lte=5).values_list('id', flat=True)
                q_filters &= Q(cliente_id__in=clientes_recurrentes)
            elif filtros['tipo_cliente'] == 'vip':
                # Clientes con 6+ reservas
                clientes_vip = Usuario.objects.annotate(
                    num_reservas=Count('reservas')
                ).filter(num_reservas__gte=6).values_list('id', flat=True)
                q_filters &= Q(cliente_id__in=clientes_vip)
        
        # ============ FILTROS DE CAMPAÑA ============
        # Filtro por campaña/promoción
        if 'con_campana' in filtros and filtros['con_campana']:
            q_filters &= Q(paquete__campania__isnull=False)
        
        if 'campana_id' in filtros:
            q_filters &= Q(paquete__campania_id=filtros['campana_id'])
        
        return queryset.filter(q_filters)
    
    @staticmethod
    def reporte_ventas_general(filtros: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera reporte general de ventas con métricas agregadas.
        """
        reservas = Reserva.objects.all()
        reservas = GeneradorReportes.aplicar_filtros(reservas, filtros)
        
        # Límite para top productos/clientes (por defecto 5, o el especificado)
        limite = filtros.get('limite', 5)
        
        # Métricas agregadas
        metricas = reservas.aggregate(
            total_ventas=Sum('total'),
            cantidad_reservas=Count('id'),
            ticket_promedio=Avg('total'),
            total_pagado=Sum('total', filter=Q(estado__in=['PAGADA', 'COMPLETADA']))
        )
        
        # Ventas por producto
        ventas_paquetes = reservas.filter(paquete__isnull=False).aggregate(
            total=Sum('total'),
            cantidad=Count('id')
        )
        ventas_servicios = reservas.filter(servicio__isnull=False).aggregate(
            total=Sum('total'),
            cantidad=Count('id')
        )
        
        # Top productos
        top_paquetes = (
            reservas.filter(paquete__isnull=False)
            .values('paquete__nombre', 'paquete__id')
            .annotate(
                total_ventas=Sum('total'),
                cantidad=Count('id')
            )
            .order_by('-total_ventas')[:limite]
        )
        
        top_servicios = (
            reservas.filter(servicio__isnull=False)
            .values('servicio__titulo', 'servicio__id')
            .annotate(
                total_ventas=Sum('total'),
                cantidad=Count('id')
            )
            .order_by('-total_ventas')[:limite]
        )
        
        # Top clientes
        top_clientes = (
            reservas.values('cliente__nombre', 'cliente__id')
            .annotate(
                total_gastado=Sum('total'),
                cantidad_reservas=Count('id')
            )
            .order_by('-total_gastado')[:limite * 2]  # Doble para clientes
        )
        
        return {
            'filtros_aplicados': filtros,
            'metricas_generales': metricas,
            'ventas_por_tipo': {
                'paquetes': ventas_paquetes,
                'servicios': ventas_servicios
            },
            'top_paquetes': list(top_paquetes),
            'top_servicios': list(top_servicios),
            'top_clientes': list(top_clientes),
            'periodo': {
                'fecha_inicio': filtros.get('fecha_inicio'),
                'fecha_fin': filtros.get('fecha_fin')
            }
        }
    
    @staticmethod
    def reporte_clientes_detallado(filtros: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reporte detallado de clientes con historial de compras.
        """
        reservas = Reserva.objects.all()
        reservas = GeneradorReportes.aplicar_filtros(reservas, filtros)
        
        # Agrupado por cliente
        clientes_data = (
            reservas.values('cliente__id', 'cliente__nombre', 'cliente__user__email')
            .annotate(
                total_gastado=Sum('total'),
                cantidad_reservas=Count('id'),
                reservas_pagadas=Count('id', filter=Q(estado__in=['PAGADA', 'COMPLETADA'])),
                reservas_canceladas=Count('id', filter=Q(estado='CANCELADA')),
                ticket_promedio=Avg('total'),
                ultima_compra=Max('fecha')
            )
            .order_by('-total_gastado')
        )
        
        return {
            'filtros_aplicados': filtros,
            'cantidad_clientes': clientes_data.count(),
            'clientes': list(clientes_data),
            'resumen': {
                'total_facturado': sum(c['total_gastado'] or 0 for c in clientes_data),
                'promedio_por_cliente': clientes_data.aggregate(Avg('total_gastado'))
            }
        }
    
    @staticmethod
    def reporte_productos_rendimiento(filtros: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reporte de rendimiento de productos (servicios y paquetes).
        """
        reservas = Reserva.objects.all()
        reservas = GeneradorReportes.aplicar_filtros(reservas, filtros)
        
        # Análisis de paquetes
        paquetes = (
            reservas.filter(paquete__isnull=False)
            .values(
                'paquete__id',
                'paquete__nombre',
                'paquete__precio_base',
                'paquete__es_personalizado'
            )
            .annotate(
                ventas_totales_bob=Sum('total'),
                cantidad_vendida=Count('id'),
                tasa_conversion=Count('id', filter=Q(estado__in=['PAGADA', 'COMPLETADA'])) * 100.0 / Count('id')
            )
            .order_by('-ventas_totales_bob')
        )
        
        # Convertir ventas a USD (dividir por 6.96) y agregar ambas monedas
        paquetes_lista = []
        for p in paquetes:
            paquetes_lista.append({
                'paquete__id': p['paquete__id'],
                'paquete__nombre': p['paquete__nombre'],
                'paquete__precio_base_usd': float(p['paquete__precio_base']),
                'paquete__precio_base_bob': float(p['paquete__precio_base']) * 6.96,
                'paquete__es_personalizado': p['paquete__es_personalizado'],
                'ventas_totales_bob': float(p['ventas_totales_bob'] or 0),
                'ventas_totales_usd': float(p['ventas_totales_bob'] or 0) / 6.96,
                'cantidad_vendida': p['cantidad_vendida'],
                'tasa_conversion': float(p['tasa_conversion']),
            })
        paquetes = paquetes_lista
        
        # Análisis de servicios
        servicios = (
            reservas.filter(servicio__isnull=False)
            .values(
                'servicio__id',
                'servicio__titulo',
                'servicio__precio_usd',
                'servicio__categoria__nombre'
            )
            .annotate(
                ventas_totales_bob=Sum('total'),
                cantidad_vendida=Count('id'),
                tasa_conversion=Count('id', filter=Q(estado__in=['PAGADA', 'COMPLETADA'])) * 100.0 / Count('id')
            )
            .order_by('-ventas_totales_bob')
        )
        
        # Convertir ventas a USD y agregar ambas monedas
        servicios_lista = []
        for s in servicios:
            servicios_lista.append({
                'servicio__id': s['servicio__id'],
                'servicio__titulo': s['servicio__titulo'],
                'servicio__precio_usd': float(s['servicio__precio_usd']),
                'servicio__precio_bob': float(s['servicio__precio_usd']) * 6.96,
                'servicio__categoria__nombre': s['servicio__categoria__nombre'],
                'ventas_totales_bob': float(s['ventas_totales_bob'] or 0),
                'ventas_totales_usd': float(s['ventas_totales_bob'] or 0) / 6.96,
                'cantidad_vendida': s['cantidad_vendida'],
                'tasa_conversion': float(s['tasa_conversion']),
            })
        servicios = servicios_lista
        
        return {
            'filtros_aplicados': filtros,
            'paquetes': paquetes,
            'servicios': servicios,
            'resumen': {
                'total_paquetes_vendidos': sum(p['cantidad_vendida'] for p in paquetes),
                'total_servicios_vendidos': sum(s['cantidad_vendida'] for s in servicios),
                'ingresos_paquetes_bob': sum(p['ventas_totales_bob'] or 0 for p in paquetes),
                'ingresos_paquetes_usd': sum(p['ventas_totales_usd'] or 0 for p in paquetes),
                'ingresos_servicios_bob': sum(s['ventas_totales_bob'] or 0 for s in servicios),
                'ingresos_servicios_usd': sum(s['ventas_totales_usd'] or 0 for s in servicios)
            }
        }
    
    @staticmethod
    def reporte_por_comando_voz(comando: str) -> Dict[str, Any]:
        """
        Genera un reporte basado en un comando de voz interpretado.
        
        Ejemplo:
        >>> GeneradorReportes.reporte_por_comando_voz(
        ...     "dame las ventas desde el 1/1/2025 hasta hoy de paquetes mayores a 1000"
        ... )
        """
        # Interpretar comando
        filtros = InterpretadorComandosVoz.interpretar(comando)
        
        # Generar reporte general
        return GeneradorReportes.reporte_ventas_general(filtros)
