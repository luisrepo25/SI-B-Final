"""
Endpoints de API para reportes avanzados con IA y gráficas interactivas.
CU19 - Reportes avanzados (estáticos y dinámicos) y por voz
CU20 - API de Gráficas Interactivas

Implementado: v2.3.0
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Avg, Q, F, Max, Min, Case, When, DecimalField, Value
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import json

from .models import Reserva, Pago, Usuario, Servicio, Paquete, Visitante
from .ia_processor import ReportesIAProcessor
from .reportes import InterpretadorComandosVoz
from .export_utils import exportar_reporte_pdf, exportar_reporte_excel, exportar_reporte_docx


# ============================================================================
# 🎤 ENDPOINT: Procesar Comando de Voz con IA
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def procesar_comando_ia(request):
    """
    POST /api/reportes/ia/procesar/
    
    Procesa comandos de voz/texto en lenguaje natural usando IA (OpenAI GPT-4o-mini)
    con fallback a procesamiento local si la IA no está disponible.
    
    Request Body:
    {
        "comando" | "prompt" | "texto": "dame reportes de ventas de santa cruz del mes pasado en excel",
        "contexto": "reportes"  // opcional
    }
    
    Response:
    {
        "success": true,
        "interpretacion": "Reporte de ventas de Santa Cruz del mes anterior",
        "accion": "generar_reporte",
        "tipo_reporte": "ventas",
        "formato": "excel",
        "filtros": {
            "departamento": "Santa Cruz",
            "fecha_inicio": "2025-10-01",
            "fecha_fin": "2025-10-31",
            "moneda": "BOB"
        },
        "respuesta_texto": "Generaré un reporte de ventas de Santa Cruz del mes pasado en Excel",
        "confianza": 0.95,
        "usando_ia": true
    }
    
    Versión: 2.3.0
    """
    try:
        # Validar request (aceptar alias usados por el frontend: prompt/texto)
        comando_raw = (
            request.data.get('comando')
            or request.data.get('prompt')
            or request.data.get('texto')
            or ''
        )
        comando = comando_raw.strip()
        if not comando:
            return Response({
                'success': False,
                'error': 'El campo "comando" (o alias "prompt"/"texto") es requerido y no puede estar vacío'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        contexto = request.data.get('contexto', 'reportes')
        
        # Procesar con IA
        processor = ReportesIAProcessor()
        resultado = processor.procesar_comando(comando, contexto)
        
        # Agregar información adicional
        usando_ia = processor.client is not None
        resultado['success'] = True
        resultado['usando_ia'] = usando_ia
        # Señalizar disponibilidad de IA y motivo del fallback (si aplica)
        resultado['ia_disponible'] = usando_ia
        if not usando_ia:
            resultado['motivo_fallback'] = 'OPENAI_API_KEY no configurada o cliente no inicializado'
        resultado['comando_original'] = comando
        
        # Log de la operación
        print(f"✅ Comando procesado: {comando}")
        print(f"📊 Tipo: {resultado.get('tipo_reporte')}, Formato: {resultado.get('formato')}")
        print(f"🎯 Confianza: {resultado.get('confianza', 0):.2%}")
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error en procesar_comando_ia: {e}")
        return Response({
            'success': False,
            'error': 'Error al procesar el comando',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# 📊 ENDPOINT: Obtener Datos para Gráficas Interactivas
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def obtener_datos_graficas(request):
    """
    POST /api/reportes/graficas/
    
    Retorna datos agregados para gráficas interactivas en el dashboard.
    
    Request Body:
    {
        "fecha_inicio": "2025-01-01",      // opcional
        "fecha_fin": "2025-12-31",         // opcional
        "departamento": "Santa Cruz",      // opcional
        "moneda": "BOB",                   // opcional: "BOB" o "USD", default: "BOB"
        "tipo_cliente": "nuevo",           // opcional: "nuevo", "recurrente", "vip"
        "agrupar_por": "mes"               // opcional: "mes", "departamento", "dia"
    }
    
    Response:
    {
        "success": true,
        "moneda": "BOB",
        "periodo": {
            "fecha_inicio": "2025-01-01",
            "fecha_fin": "2025-12-31"
        },
        "metricas": {
            "total_ventas": 125450.50,
            "total_reservas": 342,
            "promedio_venta": 367.11,
            "total_clientes": 156,
            "tasa_conversion": 68.5
        },
        "ventas_por_mes": [
            {"mes": "2025-01", "mes_nombre": "Enero 2025", "total": 12500.00, "cantidad": 28},
            ...
        ],
        "ventas_por_departamento": [
            {"departamento": "Santa Cruz", "total": 45000.00, "porcentaje": 35.9},
            ...
        ],
        "productos_mas_vendidos": [
            {
                "id": 5,
                "nombre": "Tour Salar de Uyuni",
                "tipo": "paquete",
                "total_ventas": 18500.00,
                "cantidad_vendida": 42,
                "promedio": 440.48
            },
            ...
        ],
        "tipos_cliente": [
            {"tipo": "nuevo", "cantidad": 89, "porcentaje": 57.1},
            {"tipo": "recurrente", "cantidad": 67, "porcentaje": 42.9}
        ],
        "tendencia_mensual": [
            {"mes": "2025-01", "ventas": 12500, "reservas": 28, "crecimiento": 15.3},
            ...
        ]
    }
    
    Versión: 2.3.0
    """
    try:
        # Extraer filtros del request
        filtros = request.data
        
        fecha_inicio = filtros.get('fecha_inicio')
        fecha_fin = filtros.get('fecha_fin')
        departamento = filtros.get('departamento')
        moneda = filtros.get('moneda', 'BOB')
        tipo_cliente = filtros.get('tipo_cliente')
        
        # Validar moneda
        if moneda not in ['BOB', 'USD']:
            moneda = 'BOB'
        
        # Tasa de conversión BOB -> USD
        TASA_CAMBIO = Decimal('6.96')
        
        # Query base de reservas
        queryset = Reserva.objects.filter(
            estado__in=['CONFIRMADA', 'COMPLETADA', 'PAGADA']
        )
        
        # Aplicar filtro de fechas
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__gte=fecha_inicio_dt)
            except ValueError:
                pass
        else:
            # Por defecto: último año
            fecha_inicio_dt = (timezone.now() - timedelta(days=365)).date()
            queryset = queryset.filter(fecha__gte=fecha_inicio_dt)
            fecha_inicio = fecha_inicio_dt.strftime('%Y-%m-%d')
        
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__lte=fecha_fin_dt)
            except ValueError:
                pass
        else:
            fecha_fin_dt = timezone.now().date()
            fecha_fin = fecha_fin_dt.strftime('%Y-%m-%d')
        
        # Aplicar filtro de departamento
        if departamento:
            queryset = queryset.filter(
                Q(paquete__departamento__iexact=departamento) |
                Q(servicio__departamento__iexact=departamento)
            )
        
        # Aplicar filtro de tipo de cliente
        if tipo_cliente:
            if tipo_cliente == 'nuevo':
                # Clientes con solo 1 reserva
                queryset = queryset.annotate(
                    num_reservas=Count('usuario__reserva')
                ).filter(num_reservas=1)
            elif tipo_cliente == 'recurrente':
                # Clientes con 2-5 reservas
                queryset = queryset.annotate(
                    num_reservas=Count('usuario__reserva')
                ).filter(num_reservas__gte=2, num_reservas__lte=5)
            elif tipo_cliente == 'vip':
                # Clientes con 6+ reservas
                queryset = queryset.annotate(
                    num_reservas=Count('usuario__reserva')
                ).filter(num_reservas__gte=6)
        
        # ========== MÉTRICAS PRINCIPALES ==========
        
        metricas_query = queryset.aggregate(
            total_ventas=Sum('total'),
            total_reservas=Count('id'),
            promedio_venta=Avg('total'),
            total_clientes=Count('usuario', distinct=True)
        )
        
        total_ventas = metricas_query['total_ventas'] or Decimal('0')
        total_reservas = metricas_query['total_reservas'] or 0
        promedio_venta = metricas_query['promedio_venta'] or Decimal('0')
        total_clientes = metricas_query['total_clientes'] or 0
        
        # Convertir a moneda solicitada
        if moneda == 'USD':
            total_ventas = total_ventas / TASA_CAMBIO
            promedio_venta = promedio_venta / TASA_CAMBIO
        
        # Calcular tasa de conversión (reservas confirmadas / total clientes)
        tasa_conversion = (total_reservas / total_clientes * 100) if total_clientes > 0 else 0
        
        metricas = {
            'total_ventas': float(round(total_ventas, 2)),
            'total_reservas': total_reservas,
            'promedio_venta': float(round(promedio_venta, 2)),
            'total_clientes': total_clientes,
            'tasa_conversion': round(tasa_conversion, 2)
        }
        
        # ========== VENTAS POR MES ==========
        
        ventas_mes = queryset.values('fecha__year', 'fecha__month').annotate(
            total=Sum('total'),
            cantidad=Count('id')
        ).order_by('fecha__year', 'fecha__month')
        
        meses_nombres = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        ventas_por_mes = []
        for item in ventas_mes:
            año = item['fecha__year']
            mes = item['fecha__month']
            total = item['total'] or Decimal('0')
            
            if moneda == 'USD':
                total = total / TASA_CAMBIO
            
            ventas_por_mes.append({
                'mes': f"{año}-{mes:02d}",
                'mes_nombre': f"{meses_nombres[mes]} {año}",
                'total': float(round(total, 2)),
                'cantidad': item['cantidad']
            })
        
        # ========== VENTAS POR DEPARTAMENTO ==========
        
        # Ventas de paquetes por departamento
        ventas_paquetes_dept = queryset.filter(
            paquete__isnull=False
        ).values('paquete__departamento').annotate(
            total=Sum('total')
        )
        
        # Ventas de servicios por departamento
        ventas_servicios_dept = queryset.filter(
            servicio__isnull=False
        ).values('servicio__departamento').annotate(
            total=Sum('total')
        )
        
        # Combinar ambos
        departamentos_dict = {}
        
        for item in ventas_paquetes_dept:
            dept = item['paquete__departamento'] or 'Sin especificar'
            departamentos_dict[dept] = departamentos_dict.get(dept, Decimal('0')) + (item['total'] or Decimal('0'))
        
        for item in ventas_servicios_dept:
            dept = item['servicio__departamento'] or 'Sin especificar'
            departamentos_dict[dept] = departamentos_dict.get(dept, Decimal('0')) + (item['total'] or Decimal('0'))
        
        # Convertir a lista y calcular porcentajes
        ventas_por_departamento = []
        total_general = sum(departamentos_dict.values())
        
        for dept, total in sorted(departamentos_dict.items(), key=lambda x: x[1], reverse=True):
            if moneda == 'USD':
                total = total / TASA_CAMBIO
            
            porcentaje = (total / total_general * 100) if total_general > 0 else 0
            
            ventas_por_departamento.append({
                'departamento': dept,
                'total': float(round(total, 2)),
                'porcentaje': round(porcentaje, 2)
            })
        
        # ========== PRODUCTOS MÁS VENDIDOS ==========
        
        # Paquetes más vendidos
        paquetes_vendidos = queryset.filter(paquete__isnull=False).values(
            'paquete__id', 'paquete__nombre'
        ).annotate(
            total_ventas=Sum('total'),
            cantidad_vendida=Count('id'),
            promedio=Avg('total')
        ).order_by('-total_ventas')[:10]
        
        # Servicios más vendidos
        servicios_vendidos = queryset.filter(servicio__isnull=False).values(
            'servicio__id', 'servicio__nombre'
        ).annotate(
            total_ventas=Sum('total'),
            cantidad_vendida=Count('id'),
            promedio=Avg('total')
        ).order_by('-total_ventas')[:10]
        
        productos_mas_vendidos = []
        
        for item in paquetes_vendidos:
            total = item['total_ventas'] or Decimal('0')
            promedio = item['promedio'] or Decimal('0')
            
            if moneda == 'USD':
                total = total / TASA_CAMBIO
                promedio = promedio / TASA_CAMBIO
            
            productos_mas_vendidos.append({
                'id': item['paquete__id'],
                'nombre': item['paquete__nombre'],
                'tipo': 'paquete',
                'total_ventas': float(round(total, 2)),
                'cantidad_vendida': item['cantidad_vendida'],
                'promedio': float(round(promedio, 2))
            })
        
        for item in servicios_vendidos:
            total = item['total_ventas'] or Decimal('0')
            promedio = item['promedio'] or Decimal('0')
            
            if moneda == 'USD':
                total = total / TASA_CAMBIO
                promedio = promedio / TASA_CAMBIO
            
            productos_mas_vendidos.append({
                'id': item['servicio__id'],
                'nombre': item['servicio__nombre'],
                'tipo': 'servicio',
                'total_ventas': float(round(total, 2)),
                'cantidad_vendida': item['cantidad_vendida'],
                'promedio': float(round(promedio, 2))
            })
        
        # Ordenar por total_ventas y tomar top 10
        productos_mas_vendidos = sorted(
            productos_mas_vendidos,
            key=lambda x: x['total_ventas'],
            reverse=True
        )[:10]
        
        # ========== TIPOS DE CLIENTE ==========
        
        # Clasificar clientes por número de reservas
        clientes_con_reservas = Usuario.objects.annotate(
            num_reservas=Count('reservas', filter=Q(
                reservas__fecha__gte=fecha_inicio_dt,
                reservas__fecha__lte=fecha_fin_dt,
                reservas__estado__in=['CONFIRMADA', 'COMPLETADA', 'PAGADA']
            ))
        ).filter(num_reservas__gt=0)
        
        nuevos = clientes_con_reservas.filter(num_reservas=1).count()
        recurrentes = clientes_con_reservas.filter(num_reservas__gte=2, num_reservas__lte=5).count()
        vip = clientes_con_reservas.filter(num_reservas__gte=6).count()
        
        total_clasificados = nuevos + recurrentes + vip
        
        tipos_cliente = []
        if total_clasificados > 0:
            tipos_cliente = [
                {
                    'tipo': 'nuevo',
                    'cantidad': nuevos,
                    'porcentaje': round(nuevos / total_clasificados * 100, 2)
                },
                {
                    'tipo': 'recurrente',
                    'cantidad': recurrentes,
                    'porcentaje': round(recurrentes / total_clasificados * 100, 2)
                },
                {
                    'tipo': 'vip',
                    'cantidad': vip,
                    'porcentaje': round(vip / total_clasificados * 100, 2)
                }
            ]
        
        # ========== TENDENCIA MENSUAL ==========
        
        tendencia_mensual = []
        ventas_mes_lista = list(ventas_mes)
        
        for i, item in enumerate(ventas_mes_lista):
            año = item['fecha__year']
            mes = item['fecha__month']
            total = item['total'] or Decimal('0')
            cantidad = item['cantidad']
            
            if moneda == 'USD':
                total = total / TASA_CAMBIO
            
            # Calcular crecimiento respecto al mes anterior
            crecimiento = 0.0
            if i > 0:
                total_anterior = ventas_mes_lista[i-1]['total'] or Decimal('0')
                if total_anterior > 0:
                    if moneda == 'USD':
                        total_anterior = total_anterior / TASA_CAMBIO
                    crecimiento = ((total - total_anterior) / total_anterior * 100)
            
            tendencia_mensual.append({
                'mes': f"{año}-{mes:02d}",
                'mes_nombre': f"{meses_nombres[mes]} {año}",
                'ventas': float(round(total, 2)),
                'reservas': cantidad,
                'crecimiento': round(crecimiento, 2)
            })
        
        # ========== RESPUESTA FINAL ==========
        
        respuesta = {
            'success': True,
            'moneda': moneda,
            'tasa_cambio': float(TASA_CAMBIO) if moneda == 'USD' else None,
            'periodo': {
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin
            },
            'filtros_aplicados': {
                'departamento': departamento,
                'tipo_cliente': tipo_cliente
            },
            'metricas': metricas,
            'ventas_por_mes': ventas_por_mes,
            'ventas_por_departamento': ventas_por_departamento,
            'productos_mas_vendidos': productos_mas_vendidos,
            'tipos_cliente': tipos_cliente,
            'tendencia_mensual': tendencia_mensual
        }
        
        print(f"✅ Datos de gráficas generados: {total_reservas} reservas, {moneda}")
        
        return Response(respuesta, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error en obtener_datos_graficas: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': 'Error al obtener datos de gráficas',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# 📄 ENDPOINTS: Generar Reportes Descargables
# ============================================================================

@api_view(['GET'])
@permission_classes([])
def generar_reporte_ventas(request):
    """
    GET /api/reportes/ventas/
    
    Genera y descarga reporte de ventas en formato PDF, Excel o DOCX.
    
    Query Parameters:
        - formato: pdf | excel | docx (default: pdf)
        - fecha_inicio: YYYY-MM-DD
        - fecha_fin: YYYY-MM-DD
        - departamento: string
        - moneda: BOB | USD (default: BOB)
        - monto_minimo: número
        - monto_maximo: número
    
    Response: Archivo descargable
    
    Versión: 2.3.0
    """
    try:
        # Extraer parámetros
        formato = request.GET.get('formato', 'pdf').lower()
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        departamento = request.GET.get('departamento')
        moneda = request.GET.get('moneda', 'BOB').upper()
        monto_minimo = request.GET.get('monto_minimo')
        monto_maximo = request.GET.get('monto_maximo')
        
        # Construir filtros
        filtros = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'departamento': departamento,
            'moneda': moneda,
        }
        
        if monto_minimo:
            filtros['monto_minimo'] = float(monto_minimo)
        if monto_maximo:
            filtros['monto_maximo'] = float(monto_maximo)
        
        # Query de reservas
        queryset = Reserva.objects.filter(
            estado__in=['CONFIRMADA', 'COMPLETADA', 'PAGADA']
        ).select_related('cliente', 'paquete', 'servicio')
        
        # Aplicar filtros
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if departamento:
            queryset = queryset.filter(
                Q(paquete__departamento__iexact=departamento) |
                Q(servicio__departamento__iexact=departamento)
            )
        
        # Preparar datos
        datos = []
        for reserva in queryset:
            datos.append({
                'fecha': reserva.fecha.strftime('%d/%m/%Y'),
                'cliente': reserva.cliente.nombre if reserva.cliente else 'N/A',
                'producto': reserva.paquete.nombre if reserva.paquete else (reserva.servicio.titulo if reserva.servicio else 'N/A'),
                'tipo': 'Paquete' if reserva.paquete else 'Servicio',
                'monto': float(reserva.total),
                'estado': reserva.estado
            })
        
        print(f"📊 Reporte Ventas - Total reservas encontradas: {queryset.count()}")
        print(f"📊 Reporte Ventas - Datos preparados: {len(datos)} registros")
        print(f"📊 Filtros aplicados: {filtros}")
        
        # Generar reporte según formato
        if formato == 'pdf':
            archivo = exportar_reporte_pdf(datos, 'ventas', filtros)
            response = HttpResponse(archivo, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.pdf"'
        elif formato == 'excel':
            archivo = exportar_reporte_excel(datos, 'ventas', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        elif formato == 'docx':
            archivo = exportar_reporte_docx(datos, 'ventas', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="reporte_ventas_{timezone.now().strftime("%Y%m%d")}.docx"'
        else:
            return Response({
                'success': False,
                'error': 'Formato no soportado. Use: pdf, excel o docx'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"✅ Reporte de ventas generado: {formato}, {len(datos)} registros")
        return response
        
    except Exception as e:
        print(f"❌ Error en generar_reporte_ventas: {e}")
        return Response({
            'success': False,
            'error': 'Error al generar reporte',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generar_reporte_clientes(request):
    """
    GET /api/reportes/clientes/
    
    Genera y descarga reporte de clientes.
    Similar a generar_reporte_ventas pero enfocado en datos de clientes.
    
    Versión: 2.3.0
    """
    try:
        formato = request.GET.get('formato', 'pdf').lower()
        moneda = request.GET.get('moneda', 'USD').upper()
        tipo_cliente = request.GET.get('tipo_cliente')  # nuevo, recurrente, vip
        departamento = request.GET.get('departamento')
        ciudad = request.GET.get('ciudad')
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        # Filtro por estado solicitado (pagada/confirmada/completada), acepta múltiples valores separados por coma
        estado_param = request.GET.get('estado')
        if not estado_param:
            # también soporta repetir ?estado=pagada&estado=confirmada
            estado_list = request.GET.getlist('estado')
            estado_param = ','.join(estado_list) if estado_list else None
        # Normalización de términos en español y códigos en BD
        estado_map = {
            'pagada': 'PAGADA', 'pagadas': 'PAGADA', 'pagaron': 'PAGADA',
            'confirmada': 'CONFIRMADA', 'confirmadas': 'CONFIRMADA', 'confirmaron': 'CONFIRMADA',
            'completada': 'COMPLETADA', 'completadas': 'COMPLETADA', 'finalizada': 'COMPLETADA',
        }
        if estado_param:
            estados = []
            for token in estado_param.split(','):
                t = token.strip().lower()
                if not t:
                    continue
                estados.append(estado_map.get(t, t.upper()))
            # validar valores permitidos, fallback a lista por defecto si quedaron vacíos
            estados_validos = [e for e in estados if e in ['PAGADA', 'CONFIRMADA', 'COMPLETADA']]
            if not estados_validos:
                estados_validos = ['CONFIRMADA', 'COMPLETADA', 'PAGADA']
        else:
            estados_validos = ['CONFIRMADA', 'COMPLETADA', 'PAGADA']

        # Query de usuarios con reservas
        filtros_reserva_clientes = Q(reservas__estado__in=estados_validos)
        if fecha_inicio:
            filtros_reserva_clientes &= Q(reservas__fecha__gte=fecha_inicio)
        if fecha_fin:
            filtros_reserva_clientes &= Q(reservas__fecha__lte=fecha_fin)
        # Filtro por ubicación (aplica a paquete o servicio de la reserva)
        if departamento:
            filtros_reserva_clientes &= (
                Q(reservas__paquete__departamento__icontains=departamento) |
                Q(reservas__servicio__departamento__icontains=departamento)
            )
        if ciudad:
            filtros_reserva_clientes &= (
                Q(reservas__paquete__ciudad__icontains=ciudad) |
                Q(reservas__servicio__ciudad__icontains=ciudad)
            )
        
        usuarios = Usuario.objects.annotate(
            num_reservas=Count('reservas', filter=filtros_reserva_clientes),
            reservas_pagadas=Count('reservas', filter=filtros_reserva_clientes & Q(reservas__estado='PAGADA')),
            reservas_confirmadas=Count('reservas', filter=filtros_reserva_clientes & Q(reservas__estado='CONFIRMADA')),
            reservas_completadas=Count('reservas', filter=filtros_reserva_clientes & Q(reservas__estado='COMPLETADA')),
            ultima_compra=Max('reservas__fecha', filter=filtros_reserva_clientes),
            # Total gastado en USD (convirtiendo BOB)
            total_gastado_usd=Sum(
                Case(
                    When(reservas__moneda='USD', then=F('reservas__total')),
                    When(reservas__moneda='BOB', then=F('reservas__total') / 6.96),
                    default=0,
                    output_field=DecimalField()
                ),
                filter=filtros_reserva_clientes
            ),
            # Total gastado en BOB (convirtiendo USD)
            total_gastado_bob=Sum(
                Case(
                    When(reservas__moneda='BOB', then=F('reservas__total')),
                    When(reservas__moneda='USD', then=F('reservas__total') * 6.96),
                    default=0,
                    output_field=DecimalField()
                ),
                filter=filtros_reserva_clientes
            )
        ).filter(num_reservas__gt=0)
        
        # Filtrar por tipo
        if tipo_cliente == 'nuevo':
            usuarios = usuarios.filter(num_reservas=1)
        elif tipo_cliente == 'recurrente':
            usuarios = usuarios.filter(num_reservas__gte=2, num_reservas__lte=5)
        elif tipo_cliente == 'vip':
            usuarios = usuarios.filter(num_reservas__gte=6)
        
        # Preparar datos
        datos = []
        for usuario in usuarios:
            datos.append({
                'nombre': usuario.nombre,
                'email': usuario.user.email if usuario.user else 'N/A',
                'num_reservas': usuario.num_reservas,
                'reservas_pagadas': getattr(usuario, 'reservas_pagadas', 0) or 0,
                'reservas_confirmadas': getattr(usuario, 'reservas_confirmadas', 0) or 0,
                'reservas_completadas': getattr(usuario, 'reservas_completadas', 0) or 0,
                'ultima_compra': getattr(usuario, 'ultima_compra', None),
                'total_gastado_usd': float(usuario.total_gastado_usd or 0),
                'total_gastado_bob': float(usuario.total_gastado_bob or 0),
                'tipo': 'VIP' if usuario.num_reservas >= 6 else ('Recurrente' if usuario.num_reservas >= 2 else 'Nuevo')
            })
        
        filtros = {
            'tipo_cliente': tipo_cliente,
            'moneda': moneda,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'estado': ','.join(estados_validos),
            'departamento': departamento,
            'ciudad': ciudad
        }
        
        # Generar según formato
        if formato == 'pdf':
            archivo = exportar_reporte_pdf(datos, 'clientes', filtros)
            response = HttpResponse(archivo, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.pdf"'
        elif formato == 'excel':
            archivo = exportar_reporte_excel(datos, 'clientes', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        elif formato == 'docx':
            archivo = exportar_reporte_docx(datos, 'clientes', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="reporte_clientes_{timezone.now().strftime("%Y%m%d")}.docx"'
        else:
            return Response({
                'success': False,
                'error': 'Formato no soportado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"✅ Reporte de clientes generado: {formato}, {len(datos)} registros")
        return response
        
    except Exception as e:
        print(f"❌ Error en generar_reporte_clientes: {e}")
        return Response({
            'success': False,
            'error': 'Error al generar reporte',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generar_reporte_productos(request):
    """
    GET /api/reportes/productos/
    
    Genera y descarga reporte de productos/paquetes más vendidos.
    
    Versión: 2.3.0
    """
    try:
        formato = request.GET.get('formato', 'pdf').lower()
        tipo_producto = request.GET.get('tipo')  # paquete, servicio
        moneda = request.GET.get('moneda', 'USD').upper()
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        departamento = request.GET.get('departamento')
        ciudad = request.GET.get('ciudad')
        
        datos = []
        
        # Filtros para contar reservas (se aplican en annotate)
        filtros_reserva = Q(reservas__estado__in=['CONFIRMADA', 'COMPLETADA', 'PAGADA'])
        if fecha_inicio:
            filtros_reserva &= Q(reservas__fecha__gte=fecha_inicio)
        if fecha_fin:
            filtros_reserva &= Q(reservas__fecha__lte=fecha_fin)
        
        # Paquetes
        if not tipo_producto or tipo_producto == 'paquete':
            paquetes_qs = Paquete.objects.prefetch_related('servicios__categoria')
            
            # Filtrar por ubicación (estos filtros SÍ existen en Paquete)
            if departamento:
                paquetes_qs = paquetes_qs.filter(departamento__icontains=departamento)
            if ciudad:
                paquetes_qs = paquetes_qs.filter(ciudad__icontains=ciudad)
            
            paquetes = paquetes_qs.annotate(
                num_ventas=Count('reservas', filter=filtros_reserva),
                total_reservas=Count('reservas'),  # Total de reservas (incluyendo canceladas)
                # Ventas en USD: sumar las que están en USD + convertir las de BOB
                total_ventas_usd=Sum(
                    Case(
                        When(reservas__moneda='USD', then=F('reservas__total')),
                        When(reservas__moneda='BOB', then=F('reservas__total') / 6.96),
                        default=0,
                        output_field=DecimalField()
                    ),
                    filter=filtros_reserva
                ),
                # Ventas en BOB: sumar las que están en BOB + convertir las de USD
                total_ventas_bob=Sum(
                    Case(
                        When(reservas__moneda='BOB', then=F('reservas__total')),
                        When(reservas__moneda='USD', then=F('reservas__total') * 6.96),
                        default=0,
                        output_field=DecimalField()
                    ),
                    filter=filtros_reserva
                )
            ).filter(num_ventas__gt=0).order_by('-total_ventas_usd')
            
            for paquete in paquetes:
                # Obtener categoría del primer servicio del paquete
                categoria_nombre = 'Paquete Turístico'
                primer_servicio = paquete.servicios.first()
                if primer_servicio and primer_servicio.categoria:
                    categoria_nombre = primer_servicio.categoria.nombre
                
                # Calcular tasa de conversión: ventas confirmadas / total reservas
                tasa_conversion = (paquete.num_ventas / paquete.total_reservas * 100) if paquete.total_reservas > 0 else 0
                
                datos.append({
                    'nombre': paquete.nombre,
                    'tipo': 'Paquete',
                    'categoria': categoria_nombre,
                    'departamento': paquete.departamento or 'N/A',
                    'precio': float(paquete.precio_base),
                    'num_ventas': paquete.num_ventas,
                    'total_ventas_usd': float(paquete.total_ventas_usd or 0),
                    'total_ventas_bob': float(paquete.total_ventas_bob or 0),
                    'tasa_conversion': round(tasa_conversion, 1)
                })
        
        # Servicios
        if not tipo_producto or tipo_producto == 'servicio':
            servicios_qs = Servicio.objects.select_related('categoria')
            
            # Filtrar por ubicación
            if departamento:
                servicios_qs = servicios_qs.filter(departamento__icontains=departamento)
            if ciudad:
                servicios_qs = servicios_qs.filter(ciudad__icontains=ciudad)
            
            servicios = servicios_qs.annotate(
                num_ventas=Count('reservas', filter=filtros_reserva),
                total_reservas=Count('reservas'),  # Total de reservas (incluyendo canceladas)
                # Ventas en USD
                total_ventas_usd=Sum(
                    Case(
                        When(reservas__moneda='USD', then=F('reservas__total')),
                        When(reservas__moneda='BOB', then=F('reservas__total') / 6.96),
                        default=0,
                        output_field=DecimalField()
                    ),
                    filter=filtros_reserva
                ),
                # Ventas en BOB
                total_ventas_bob=Sum(
                    Case(
                        When(reservas__moneda='BOB', then=F('reservas__total')),
                        When(reservas__moneda='USD', then=F('reservas__total') * 6.96),
                        default=0,
                        output_field=DecimalField()
                    ),
                    filter=filtros_reserva
                )
            ).filter(num_ventas__gt=0).order_by('-total_ventas_usd')
            
            for servicio in servicios:
                # Calcular tasa de conversión: ventas confirmadas / total reservas
                tasa_conversion = (servicio.num_ventas / servicio.total_reservas * 100) if servicio.total_reservas > 0 else 0
                
                datos.append({
                    'nombre': servicio.titulo,
                    'tipo': 'Servicio',
                    'categoria': servicio.categoria.nombre if servicio.categoria else 'N/A',
                    'departamento': servicio.departamento or 'N/A',
                    'precio': float(servicio.precio_usd),
                    'num_ventas': servicio.num_ventas,
                    'total_ventas_usd': float(servicio.total_ventas_usd or 0),
                    'total_ventas_bob': float(servicio.total_ventas_bob or 0),
                    'tasa_conversion': round(tasa_conversion, 1)
                })
        
        # Ordenar por total_ventas_usd
        datos = sorted(datos, key=lambda x: x['total_ventas_usd'], reverse=True)
        
        print(f"📦 Reporte Productos - Total productos encontrados: {len(datos)}")
        print(f"📦 Primeros 3 productos: {datos[:3] if datos else 'VACÍO'}")
        
        # Construir filtros completos para el reporte
        filtros = {
            'tipo_producto': tipo_producto,
            'moneda': moneda,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'departamento': departamento,
            'ciudad': ciudad
        }
        
        # Generar según formato
        if formato == 'pdf':
            archivo = exportar_reporte_pdf(datos, 'productos', filtros)
            response = HttpResponse(archivo, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.pdf"'
        elif formato == 'excel':
            archivo = exportar_reporte_excel(datos, 'productos', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        elif formato == 'docx':
            archivo = exportar_reporte_docx(datos, 'productos', filtros)
            response = HttpResponse(archivo, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="reporte_productos_{timezone.now().strftime("%Y%m%d")}.docx"'
        else:
            return Response({
                'success': False,
                'error': 'Formato no soportado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"✅ Reporte de productos generado: {formato}, {len(datos)} registros")
        return response
        
    except Exception as e:
        print(f"❌ Error en generar_reporte_productos: {e}")
        return Response({
            'success': False,
            'error': 'Error al generar reporte',
            'detalle': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


