"""
Procesador de comandos de voz/texto con IA para generación de reportes.
Usa OpenAI GPT para interpretar lenguaje natural y extraer filtros estructurados.
"""
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from openai import OpenAI
from django.conf import settings


class ReportesIAProcessor:
    """
    Procesa comandos en lenguaje natural para generar reportes usando IA.
    """
    
    # Mapeo de departamentos (variantes)
    DEPARTAMENTOS = {
        'la paz': 'La Paz',
        'lapaz': 'La Paz',
        'paz': 'La Paz',
        'santa cruz': 'Santa Cruz',
        'santacruz': 'Santa Cruz',
        'cruz': 'Santa Cruz',
        'cochabamba': 'Cochabamba',
        'cbba': 'Cochabamba',
        'oruro': 'Oruro',
        'potosi': 'Potosí',
        'potosí': 'Potosí',
        'tarija': 'Tarija',
        'sucre': 'Sucre',
        'chuquisaca': 'Chuquisaca',
        'beni': 'Beni',
        'pando': 'Pando',
    }
    
    # Mapeo de meses
    MESES = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    }
    
    def __init__(self):
        """Inicializa el procesador con cliente OpenAI."""
        self.client: Optional[OpenAI] = None
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                print(f"⚠️ No se pudo inicializar OpenAI: {e}")
    
    def procesar_comando(self, prompt: str, contexto: str = "reportes") -> Dict[str, Any]:
        """
        Procesa un comando en lenguaje natural.
        
        Args:
            prompt: Comando del usuario
            contexto: Contexto de la aplicación
        
        Returns:
            Diccionario con la interpretación y filtros extraídos
        """
        # Intentar procesamiento con IA
        if self.client:
            try:
                resultado = self._procesar_con_openai(prompt, contexto)
                if resultado:
                    return resultado
            except Exception as e:
                print(f"⚠️ Error en OpenAI, usando fallback: {e}")
        
        # Fallback: procesamiento local sin IA
        return self._procesar_local(prompt)
    
    def _procesar_con_openai(self, prompt: str, contexto: str) -> Optional[Dict[str, Any]]:
        """
        Procesa el comando usando OpenAI GPT.
        """
        if not self.client:
            return None
            
        system_prompt = """
Eres un asistente especializado en reportes de turismo para Bolivia.

Tu tarea es analizar comandos en lenguaje natural y extraer información estructurada para generar reportes.

**Tipos de Reporte:**
- "paquetes" o "productos": Reportes de paquetes turísticos
- "ventas": Reportes de ventas realizadas
- "clientes": Reportes de clientes

**Formatos:**
- "pdf": Documento PDF
- "excel" o "xlsx": Hoja de cálculo Excel
- "docx" o "word": Documento Word

**Departamentos de Bolivia:**
La Paz, Santa Cruz, Cochabamba, Oruro, Potosí, Tarija, Sucre, Beni, Pando

**Filtros Posibles:**
- departamento: string (ej: "La Paz", "Santa Cruz")
- fecha_inicio: YYYY-MM-DD
- fecha_fin: YYYY-MM-DD
- monto_minimo: número
- monto_maximo: número
- tipo_cliente: "nuevo", "recurrente", "vip"
- tipo_paquete: "personalizado", "destacado"
- moneda: "USD" o "BOB"

**Acciones:**
- "generar_reporte": Generar y descargar reporte
- "consulta": Responder pregunta sin generar reporte
- "ayuda": Mostrar ayuda
- "limpiar_filtros": Resetear filtros

**RESPONDE SIEMPRE EN JSON con esta estructura exacta:**
{
  "interpretacion": "Descripción clara de lo que entendiste",
  "accion": "generar_reporte | consulta | ayuda | limpiar_filtros",
  "tipo_reporte": "paquetes | ventas | clientes | null",
  "formato": "pdf | excel | docx | null",
  "filtros": {
    "departamento": "string o null",
    "fecha_inicio": "YYYY-MM-DD o null",
    "fecha_fin": "YYYY-MM-DD o null",
    "monto_minimo": "número o null",
    "monto_maximo": "número o null",
    "tipo_cliente": "string o null",
    "tipo_paquete": "string o null",
    "moneda": "USD o BOB o null"
  },
  "respuesta_texto": "Respuesta natural al usuario",
  "confianza": 0.0-1.0
}

**Reglas importantes:**
1. Detecta fechas relativas: "mes pasado", "último trimestre", "enero", etc.
2. Normaliza departamentos a su nombre oficial
3. Detecta montos con palabras: "mil", "1000", etc.
4. Si el comando es ambiguo, asume valores por defecto razonables
5. La confianza debe reflejar qué tan seguro estás de la interpretación
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Modelo más económico y rápido
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Contexto: {contexto}\nComando: {prompt}"}
                ],
                temperature=0.3,  # Baja temperatura para respuestas más consistentes
                max_tokens=800,
                response_format={"type": "json_object"}  # Forzar respuesta JSON
            )
            
            # Verificar que hay contenido en la respuesta
            content = response.choices[0].message.content
            if not content:
                return None
                
            resultado = json.loads(content)
            
            # Validar y normalizar el resultado
            return self._validar_resultado(resultado)
            
        except Exception as e:
            print(f"❌ Error en OpenAI: {e}")
            return None
    
    def _procesar_local(self, prompt: str) -> Dict[str, Any]:
        """
        Procesamiento local básico sin IA (fallback).
        Usa regex y palabras clave simples.
        """
        prompt_lower = prompt.lower()
        
        resultado = {
            "interpretacion": f"Procesamiento local del comando: {prompt}",
            "accion": "generar_reporte",
            "tipo_reporte": None,
            "formato": "pdf",  # Por defecto PDF
            "filtros": {},
            "respuesta_texto": "",
            "confianza": 0.5  # Confianza media para procesamiento local
        }
        
        # Detectar tipo de reporte
        if any(word in prompt_lower for word in ['paquete', 'producto', 'tour']):
            resultado['tipo_reporte'] = 'paquetes'
        elif any(word in prompt_lower for word in ['venta', 'ingreso', 'ganancia']):
            resultado['tipo_reporte'] = 'ventas'
        elif any(word in prompt_lower for word in ['cliente', 'usuario', 'comprador']):
            resultado['tipo_reporte'] = 'clientes'
        else:
            resultado['tipo_reporte'] = 'paquetes'  # Por defecto
        
        # Detectar formato
        if 'excel' in prompt_lower or 'xlsx' in prompt_lower:
            resultado['formato'] = 'excel'
        elif 'word' in prompt_lower or 'docx' in prompt_lower:
            resultado['formato'] = 'docx'
        elif 'pdf' in prompt_lower:
            resultado['formato'] = 'pdf'
        
        # Detectar departamento
        for key, value in self.DEPARTAMENTOS.items():
            if key in prompt_lower:
                resultado['filtros']['departamento'] = value
                break
        
        # Detectar moneda
        if 'dólar' in prompt_lower or 'dolar' in prompt_lower or 'usd' in prompt_lower:
            resultado['filtros']['moneda'] = 'USD'
        elif 'boliviano' in prompt_lower or 'bob' in prompt_lower or 'bs' in prompt_lower:
            resultado['filtros']['moneda'] = 'BOB'
        
        # Detectar montos
        monto_match = re.search(r'mayor(?:es)?\s+(?:a|de|que)\s+(\d+)', prompt_lower)
        if monto_match:
            resultado['filtros']['monto_minimo'] = int(monto_match.group(1))
        
        monto_match = re.search(r'menor(?:es)?\s+(?:a|de|que)\s+(\d+)', prompt_lower)
        if monto_match:
            resultado['filtros']['monto_maximo'] = int(monto_match.group(1))
        
        # Detectar fechas simples (mes actual, mes pasado, etc.)
        fechas = self._extraer_fechas_basicas(prompt_lower)
        if fechas:
            resultado['filtros'].update(fechas)
        
        # Generar respuesta
        tipo_nombre = {
            'paquetes': 'paquetes turísticos',
            'ventas': 'ventas',
            'clientes': 'clientes'
        }.get(resultado['tipo_reporte'], 'reporte')
        
        formato_nombre = {
            'pdf': 'PDF',
            'excel': 'Excel',
            'docx': 'Word'
        }.get(resultado['formato'], 'PDF')
        
        departamento_texto = f" de {resultado['filtros']['departamento']}" if resultado['filtros'].get('departamento') else ""
        
        resultado['respuesta_texto'] = f"Generaré un reporte de {tipo_nombre}{departamento_texto} en formato {formato_nombre}"
        
        return resultado
    
    def _extraer_fechas_basicas(self, prompt: str) -> Dict[str, str]:
        """
        Extrae fechas básicas del prompt.
        """
        fechas = {}
        hoy = datetime.now()
        
        # Mes actual
        if 'este mes' in prompt or 'mes actual' in prompt:
            fechas['fecha_inicio'] = hoy.replace(day=1).strftime('%Y-%m-%d')
            fechas['fecha_fin'] = hoy.strftime('%Y-%m-%d')
        
        # Mes pasado
        elif 'mes pasado' in prompt or 'último mes' in prompt:
            primer_dia_mes_actual = hoy.replace(day=1)
            ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
            primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)
            fechas['fecha_inicio'] = primer_dia_mes_pasado.strftime('%Y-%m-%d')
            fechas['fecha_fin'] = ultimo_dia_mes_pasado.strftime('%Y-%m-%d')
        
        # Último trimestre
        elif 'último trimestre' in prompt or 'trimestre' in prompt:
            fecha_inicio = hoy - timedelta(days=90)
            fechas['fecha_inicio'] = fecha_inicio.strftime('%Y-%m-%d')
            fechas['fecha_fin'] = hoy.strftime('%Y-%m-%d')
        
        # Detectar mes específico
        for mes_nombre, mes_num in self.MESES.items():
            if mes_nombre in prompt:
                año = hoy.year
                if mes_num > hoy.month:
                    año -= 1  # Si el mes es futuro, usar año pasado
                
                import calendar
                ultimo_dia = calendar.monthrange(año, mes_num)[1]
                
                fechas['fecha_inicio'] = f"{año}-{mes_num:02d}-01"
                fechas['fecha_fin'] = f"{año}-{mes_num:02d}-{ultimo_dia}"
                break
        
        return fechas
    
    def _validar_resultado(self, resultado: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida y normaliza el resultado de la IA.
        """
        # Asegurar que todos los campos existan
        resultado.setdefault('interpretacion', 'Comando procesado')
        resultado.setdefault('accion', 'generar_reporte')
        resultado.setdefault('tipo_reporte', None)
        resultado.setdefault('formato', 'pdf')
        resultado.setdefault('filtros', {})
        resultado.setdefault('respuesta_texto', 'Procesando...')
        resultado.setdefault('confianza', 0.7)
        
        # Validar tipo_reporte
        if resultado['tipo_reporte'] not in ['paquetes', 'ventas', 'clientes', None]:
            resultado['tipo_reporte'] = 'paquetes'
        
        # Validar formato
        if resultado['formato'] not in ['pdf', 'excel', 'docx', None]:
            resultado['formato'] = 'pdf'
        
        # Validar accion
        if resultado['accion'] not in ['generar_reporte', 'consulta', 'ayuda', 'limpiar_filtros']:
            resultado['accion'] = 'generar_reporte'
        
        # Limpiar filtros vacíos
        filtros_limpios = {}
        for key, value in resultado['filtros'].items():
            if value is not None and value != '' and value != 'null':
                filtros_limpios[key] = value
        
        resultado['filtros'] = filtros_limpios
        
        # Asegurar que confianza esté entre 0 y 1
        resultado['confianza'] = max(0.0, min(1.0, float(resultado['confianza'])))
        
        return resultado
    
    def generar_respuesta_consulta(self, prompt: str) -> str:
        """
        Genera una respuesta a una consulta sin generar reporte.
        """
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un asistente de reportes turísticos. Responde preguntas de forma breve y útil."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=200
                )
                content = response.choices[0].message.content
                if content:
                    return content
            except Exception:
                pass
        
        # Fallback
        return "Lo siento, no puedo procesar consultas en este momento. Por favor, genera un reporte específico."
