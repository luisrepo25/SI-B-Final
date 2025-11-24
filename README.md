# 🏢 Sistema de Gestión de Condominio - Backend

Sistema backend desarrollado con Django REST Framework para la gestión integral de condominios, incluyendo reservas, pagos, paquetes personalizados y reportes avanzados.

---

## 🚀 Inicio Rápido

### **Requisitos Previos**

- Python 3.10 o superior
- pip (gestor de paquetes de Python)
- PostgreSQL (para producción) o SQLite (para desarrollo)

### **Instalación**

1. **Clonar el repositorio**

   ```bash
   git clone https://github.com/hebertsb/Backend_Spring2.git
   cd Backend_Spring2
   ```

2. **Crear entorno virtual**

   ```bash
   python -m venv .venv
   ```

3. **Activar entorno virtual**

   - Windows (PowerShell):
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - Windows (CMD):
     ```cmd
     .\.venv\Scripts\activate.bat
     ```
   - Linux/Mac:
     ```bash
     source .venv/bin/activate
     ```

4. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configurar variables de entorno**

   Crear archivo `.env` en la raíz del proyecto:

   ```env
   SECRET_KEY=tu_secret_key_aqui
   DEBUG=True
   DATABASE_URL=sqlite:///db.sqlite3
   ALLOWED_HOSTS=localhost,127.0.0.1

   # Para producción con PostgreSQL
   # DATABASE_URL=postgresql://usuario:password@host:puerto/nombre_db

   # Stripe (opcional)
   STRIPE_SECRET_KEY=tu_stripe_key

   # Dropbox (opcional)
   DROPBOX_ACCESS_TOKEN=tu_dropbox_token
   ```

6. **Ejecutar migraciones**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

7. **Crear superusuario**

   ```bash
   python manage.py createsuperuser
   ```

8. **Cargar datos iniciales (opcional)**

   ```bash
   python manage.py loaddata condominio/fixtures/datos_iniciales.json
   ```

9. **Generar datos de prueba para reportes (opcional)**

   ```bash
   python manage.py generar_datos_historicos --meses=12 --cantidad=60
   ```

10. **Iniciar servidor**
    ```bash
    python manage.py runserver
    ```

El servidor estará disponible en: `http://localhost:8000`

---

## 📦 Dependencias Principales

### **Framework Core**

- `Django==5.2.7` - Framework web
- `djangorestframework==3.16.1` - API REST
- `django-cors-headers==4.9.0` - CORS para frontend

### **Autenticación**

- `djangorestframework-simplejwt==5.5.1` - JWT tokens
- `PyJWT==2.10.1` - Manejo de tokens

### **Base de Datos**

- `psycopg2-binary==2.9.10` - PostgreSQL adapter

### **Reportes y Exportación**

- `reportlab==4.2.5` - Generación de PDF
- `openpyxl==3.1.5` - Generación de Excel
- `Pillow==11.0.0` - Procesamiento de imágenes

### **Pagos y Almacenamiento**

- `stripe==8.9.0` - Procesamiento de pagos
- `dropbox==12.0.2` - Almacenamiento en la nube

### **Utilidades**

- `django-filter==24.3` - Filtrado de queries
- `python-dotenv==1.1.1` - Variables de entorno
- `requests==2.31.0` - HTTP requests

### **Producción**

- `gunicorn==23.0.0` - WSGI server
- `whitenoise==6.11.0` - Archivos estáticos
- `dj-database-url==2.3.0` - Config de BD desde URL

---

## 🎯 Características Principales

### **1. Gestión de Reservas**

- ✅ Reservas de paquetes y servicios individuales
- ✅ Paquetes personalizados (múltiples servicios)
- ✅ Gestión de visitantes
- ✅ Bitácora de actividades

### **2. Sistema de Pagos**

- ✅ Integración con Stripe
- ✅ Comprobantes de pago
- ✅ Historial de transacciones

### **3. Reportes Avanzados (CU19)**

- ✅ Comandos de voz en español
- ✅ Fechas relativas ("hoy", "ayer", "últimos 7 días", "este mes", etc.)
- ✅ Límites dinámicos ("top 5", "primeros 10", "mejores 3")
- ✅ Exportación a PDF con formato profesional
- ✅ Exportación a Excel con múltiples hojas
- ✅ Reportes de ventas, clientes y productos

### **4. Respaldos**

- ✅ Backup automático a Dropbox
- ✅ Restauración de backups
- ✅ Backups completos de BD

---

## 📊 Endpoints de Reportes

### **Autenticación**

```bash
POST /api/token/
Body: {"username": "usuario", "password": "contraseña"}
Response: {"access": "token_jwt", "refresh": "refresh_token"}
```

### **Reportes Generales**

```bash
# Reporte de ventas
POST /api/reportes/ventas/
Headers: Authorization: Bearer {token}
Body: {
  "fecha_inicio": "2025-10-01",
  "fecha_fin": "2025-10-31",
  "formato": "pdf"  // "json" | "pdf" | "excel"
}

# Reporte de clientes
POST /api/reportes/clientes/
Body: {"formato": "excel"}

# Reporte de productos
POST /api/reportes/productos/
Body: {"formato": "pdf"}

# Dashboard
GET /api/reportes/dashboard/
```

### **Reportes por Voz**

```bash
POST /api/reportes/voz/
Body: {
  "comando": "ventas de los últimos 7 días en PDF"
}
# Descarga automática del archivo según formato detectado
```

### **Ejemplos de Comandos de Voz**

- `"ventas de hoy"`
- `"últimos 30 días en Excel"`
- `"top 5 paquetes en PDF"`
- `"clientes de este mes"`
- `"top 10 productos mayores a 1000 en Excel"`

---

## 🧪 Pruebas

### **Ejecutar tests**

```bash
python manage.py test
```

### **Probar reportes**

```bash
python scripts/test_reportes_mejorados.py
```

### **Verificar instalación**

```bash
python manage.py check
```

---

## 📁 Estructura del Proyecto

```
Backend_Spring2/
├── config/              # Configuración Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── condominio/          # App principal
│   ├── models.py        # Modelos de datos
│   ├── api.py           # Endpoints API
│   ├── serializer.py    # Serializadores DRF
│   ├── reportes.py      # Sistema de reportes
│   ├── export_utils.py  # Exportación PDF/Excel
│   ├── backups/         # Sistema de respaldos
│   └── fixtures/        # Datos iniciales
├── authz/               # Autenticación y autorización
├── scripts/             # Scripts de utilidad
├── requirements.txt     # Dependencias
├── manage.py           # CLI Django
└── README.md           # Este archivo
```

---

## 🔧 Configuración Adicional

### **PostgreSQL en Producción**

1. Crear base de datos:

   ```sql
   CREATE DATABASE nombre_db;
   CREATE USER usuario WITH PASSWORD 'contraseña';
   GRANT ALL PRIVILEGES ON DATABASE nombre_db TO usuario;
   ```

2. Actualizar `.env`:
   ```env
   DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/nombre_db
   ```

### **Configurar Stripe**

1. Obtener API key desde [Stripe Dashboard](https://dashboard.stripe.com/)
2. Añadir a `.env`:
   ```env
   STRIPE_SECRET_KEY=sk_test_xxxxx
   ```

### **Configurar Dropbox**

1. Crear app en [Dropbox Developers](https://www.dropbox.com/developers)
2. Obtener access token
3. Añadir a `.env`:
   ```env
   DROPBOX_ACCESS_TOKEN=xxxxx
   ```

---

## 📝 Comandos Útiles

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recolectar archivos estáticos
python manage.py collectstatic

# Generar datos de prueba
python manage.py generar_datos_historicos --meses=12 --cantidad=60

# Ejecutar shell de Django
python manage.py shell

# Ver todas las URLs
python manage.py show_urls
```

---

## 🚀 Despliegue

### **Heroku**

```bash
heroku login
heroku create nombre-app
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

### **Railway**

```bash
railway login
railway init
railway up
railway run python manage.py migrate
```

---

## 🤝 Contribución

1. Fork el proyecto
2. Crear rama de feature (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add: AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

---

## 📄 Licencia

Este proyecto es privado y de uso académico.

---

## 👥 Autores

- **Hebert** - [@hebertsb](https://github.com/hebertsb)

---

## 📞 Soporte

Para reportar bugs o solicitar features, crear un issue en el repositorio.

---

## 🎓 Universidad

**Universidad Autónoma Gabriel René Moreno**  
Carrera: Ingeniería de Sistemas  
Materia: Sistema de Información II  
Año: 2025
