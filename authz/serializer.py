# authz/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User

from authz.models import Rol
from condominio.models import Usuario
from authz.models import UserRole
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'slug', 'nombre', 'descripcion', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserRoleSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(source='rol', queryset=Rol.objects.all(), write_only=True)

    class Meta:
        model = UserRole
        fields = ['id', 'user', 'rol', 'role_id', 'assigned_at', 'assigned_by']
        read_only_fields = ['id', 'rol', 'assigned_at', 'assigned_by']


class UserWithRolesSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    # Expose first_name and last_name so frontends can prefill edit forms without parsing full_name
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'roles', 'is_active']

    def get_roles(self, obj):
        return list(obj.user_roles.values_list('rol__slug', flat=True))

    def get_full_name(self, obj):
        # Prefer User.first_name/last_name; si no existen, usar perfil.nombre (Usuario.nombre)
        first = obj.first_name or ''
        last = obj.last_name or ''
        if first or last:
            return f"{first} {last}".strip()
        # fallback to perfil.nombre if available
        perfil = getattr(obj, 'perfil', None)
        if perfil and getattr(perfil, 'nombre', None):
            return perfil.nombre
        return ''

    def get_is_active(self, obj):
        # expose the user's is_active directly
        return bool(obj.is_active)




class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer()  # Para mostrar detalles del rol

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'rubro', 'num_viajes', 'rol']


class PublicUsuarioSerializer(serializers.ModelSerializer):
    """Serializador público utilizado en respuestas de login/register/me.
    Devuelve el perfil unido con email/username del User y el rol como objeto.
    """
    rol = RolSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.SerializerMethodField()

    telefono = serializers.CharField(read_only=True, allow_null=True)
    fecha_nacimiento = serializers.DateField(read_only=True, allow_null=True)
    genero = serializers.CharField(read_only=True, allow_null=True)
    documento_identidad = serializers.CharField(read_only=True, allow_null=True)
    pais = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'nombre', 'rol', 'num_viajes', 'telefono', 'fecha_nacimiento', 'genero', 'documento_identidad', 'pais', 'is_active']

    def get_is_active(self, obj):
        return bool(obj.user.is_active)


class MeSerializer(serializers.ModelSerializer):
    """Serializador usado por /api/users/me/ para leer y actualizar el perfil propio.
    Permite modificar campos de Usuario y algunos campos del User (first_name, last_name, email opcional).
    """
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', required=False)
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'nombre', 'rol', 'num_viajes', 'telefono', 'fecha_nacimiento', 'genero', 'documento_identidad', 'pais', 'is_active']

    def get_is_active(self, obj):
        return bool(obj.user.is_active)

    def update(self, instance, validated_data):
        # update nested user fields if provided. Some frontends send nested `user` payload
        # but because first_name/last_name are declared with source='user.first_name' they
        # may not appear in validated_data; fall back to initial_data to accept nested form.
        user_data = validated_data.pop('user', {})
        if not user_data and hasattr(self, 'initial_data'):
            user_data = self.initial_data.get('user', {}) or {}
        # Asegurarse de que user_data sea un dict
        if not isinstance(user_data, dict):
            user_data = {}
        user = instance.user
        # email change: validate uniqueness
        new_email = user_data.get('email')
        if new_email and new_email != user.email:
            if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({'email': ['Este correo ya está en uso.']})
            user.email = new_email
            user.username = new_email
        # track name updates
        first_updated = 'first_name' in user_data
        last_updated = 'last_name' in user_data
        if first_updated:
            user.first_name = user_data.get('first_name') or ''
        if last_updated:
            user.last_name = user_data.get('last_name') or ''
        user.save()

        # (No role-based privilege changes here; role handling occurs at registration)

        # If payload didn't explicitly include 'nombre', keep Usuario.nombre in sync with User first/last
        if ('nombre' not in validated_data) and (first_updated or last_updated):
            full = f"{user.first_name or ''} {user.last_name or ''}".strip()
            # only overwrite if there's something to write
            if full:
                validated_data['nombre'] = full

        # update perfil fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    # Campos que el frontend envía según la guía (aceptamos variantes y las mapeamos)
    nombres = serializers.CharField(required=True, allow_blank=False)
    apellidos = serializers.CharField(required=False, allow_blank=True)
    # Aceptar alias que el frontend pueda enviar
    lastname = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    telefono = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True)
    genero = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    documento_identidad = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pais = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # campos específicos del backend existente (mantenemos compatibilidad)
    # Use PrimaryKeyRelatedField to get DRF to validate the rol automatically
    rol = serializers.PrimaryKeyRelatedField(queryset=Rol.objects.all(), required=True)
    rubro = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        return value

    # Nota: se elimina la validación de edad (fecha_nacimiento) por petición del frontend

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({
                'password_confirm': ["Las contraseñas no coinciden."]
            })
        return attrs

    def create(self, validated_data):
        # Mapear campos del frontend al modelo existente sin tocar models.py
        nombres = validated_data.get('nombres')
        apellidos = validated_data.get('apellidos') or validated_data.get('lastname') or validated_data.get('last_name') or ''
        email = validated_data.get('email')
        password = validated_data.get('password')
        # 'rol' here is already a Rol instance due to PrimaryKeyRelatedField
        rol = validated_data.get('rol')
        rubro = validated_data.get('rubro', '')

        # Crear User
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = nombres
        user.last_name = apellidos
        user.save()

        # Crear perfil Usuario
        nombre_completo = f"{nombres} {apellidos}".strip()
        perfil = Usuario.objects.create(
            user=user,
            nombre=nombre_completo,
            rubro=rubro,
            rol=rol,
            telefono=validated_data.get('telefono') or None,
            fecha_nacimiento=validated_data.get('fecha_nacimiento') or None,
            genero=validated_data.get('genero') or None,
            documento_identidad=validated_data.get('documento_identidad') or None,
            pais=validated_data.get('pais') or None,
        )

        # If the assigned role looks administrative, mark the user as staff
        # and try to grant the `auth.change_user` permission so they can access
        # admin-like endpoints (e.g. GET /api/users/ requires staff or change_user).
        try:
            slug = (rol.slug or '').lower() if rol else ''
            nombre = (rol.nombre or '').lower() if rol else ''
            if slug in ('admin', 'administrator') or 'admin' in nombre or 'administrador' in nombre:
                user.is_staff = True
                try:
                    from django.contrib.auth.models import Permission
                    perm = Permission.objects.get(codename='change_user')
                    user.user_permissions.add(perm)
                except Exception:
                    pass
                user.save()
        except Exception:
            pass

        # Nota: campos opcionales (telefono, fecha_nacimiento, genero, etc.) no se guardan
        # porque el modelo actual no los define. Si se necesitan, debemos extender el modelo
        # y crear migraciones.
        return perfil