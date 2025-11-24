# core/recommendation_utils.py
def generar_recomendacion_equipaje(titulo_plan, usuario_id):
    """Genera una recomendación de equipaje basada en el tipo de plan"""
    
    recomendaciones_base = {
        "Plan Inicial": {
            "texto": "Perfecto para comenzar tu aventura. Equipaje básico pero esencial.",
            "items": [
                {"categoria": "Documentos", "items": ["Documento de identidad", "Reserva de servicios básicos"], "prioridad": "alta"},
                {"categoria": "Ropa Básica", "items": ["2-3 cambios de ropa", "Calzado cómodo"], "prioridad": "media"},
                {"categoria": "Higiene", "items": ["Kit básico de aseo", "Toalla pequeña"], "prioridad": "media"},
            ]
        },
        "Plan Profesional": {
            "texto": "Ideal para experiencias más completas. Equipaje mejorado.",
            "items": [
                {"categoria": "Documentos", "items": ["Documento de identidad", "Reservas confirmadas", "Seguro básico"], "prioridad": "alta"},
                {"categoria": "Ropa", "items": ["3-4 cambios de ropa", "Calzado para caminar", "Abrigo ligero"], "prioridad": "alta"},
                {"categoria": "Tecnología", "items": ["Cámara básica", "Power bank", "Adaptadores"], "prioridad": "media"},
                {"categoria": "Salud", "items": ["Botiquín básico", "Protector solar", "Repelente"], "prioridad": "media"},
            ]
        },
        "Plan Premium": {
            "texto": "Experiencia premium merece equipaje completo y especializado.",
            "items": [
                {"categoria": "Documentos", "items": ["Pasaporte/CI", "Todas las reservas", "Seguro de viaje", "Licencia internacional"], "prioridad": "alta"},
                {"categoria": "Ropa", "items": ["Ropa técnica", "Calzado especializado", "Ropa formal", "Traje de baño"], "prioridad": "alta"},
                {"categoria": "Tecnología", "items": ["Cámara profesional", "Drones (si aplica)", "Tablet/laptop", "Power bank grande"], "prioridad": "alta"},
                {"categoria": "Comodidad", "items": ["Almohada de viaje", "Audífonos noise-cancelling", "Gafas de sol polarizadas"], "prioridad": "media"},
                {"categoria": "Salud", "items": ["Botiquín completo", "Medicamentos personales", "Suplementos"], "prioridad": "alta"},
            ]
        },
        "Plan Anual Élite": {
            "texto": "Para el viajero élite que busca la máxima experiencia. Equipaje de lujo y especializado.",
            "items": [
                {"categoria": "Documentos Élite", "items": ["Pasaporte con visas", "Tarjetas de prioridad", "Miembro de aerolíneas", "Accesos VIP"], "prioridad": "alta"},
                {"categoria": "Ropa Premium", "items": ["Ropa de diseñador", "Calzado técnico premium", "Accesorios de lujo", "Ropa para eventos"], "prioridad": "alta"},
                {"categoria": "Tecnología Avanzada", "items": ["Equipo fotográfico profesional", "Dispositivos satelitales", "Tablet premium", "Cargadores inalámbricos"], "prioridad": "alta"},
                {"categoria": "Comodidad Élite", "items": ["Almohada memory foam", "Kit de bienestar", "Productos orgánicos", "Accesorios de masaje"], "prioridad": "media"},
                {"categoria": "Experiencias", "items": ["Guías especializados", "Equipo deportivo premium", "Instrumentos musicales", "Material artístico"], "prioridad": "baja"},
                {"categoria": "Seguridad", "items": ["Caja fuerte portátil", "Localizador GPS", "Seguro premium", "Asistencia 24/7"], "prioridad": "alta"},
            ]
        }
    }
    
    # Buscar recomendación por título del plan
    plan_key = next((key for key in recomendaciones_base.keys() if key.lower() in titulo_plan.lower()), "Plan Inicial")
    recomendacion = recomendaciones_base.get(plan_key, recomendaciones_base["Plan Inicial"])
    
    print(f"🎯 Recomendación generada para plan: {titulo_plan}")
    
    return recomendacion