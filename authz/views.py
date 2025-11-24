from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers

from authz.models import Rol
from .serializer import UserSerializer, UsuarioSerializer, RegisterSerializer, PublicUsuarioSerializer
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework import status
from condominio.models import Usuario, Bitacora  # importa tu modelo personalizado

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers

from authz.models import Rol
from .serializer import UserSerializer, UsuarioSerializer, RegisterSerializer, PublicUsuarioSerializer
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework import status
from condominio.models import Usuario, Bitacora  # importa tu modelo personalizado

# Create your views here.


@api_view(["POST"])
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")
    try:
        user = User.objects.get(email=email)
        # Rechazar login si el usuario está inactivo
        if not user.is_active:
            return Response({"error": "Usuario inactivo."}, status=status.HTTP_403_FORBIDDEN)
        if user.check_password(password):
            token, _ = Token.objects.get_or_create(user=user)

            try:
                perfil = user.perfil  # relación OneToOne con Usuario
                perfil_serializado = PublicUsuarioSerializer(perfil).data
                # registrar en bitacora: ingreso al sistema
                ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
                try:
                    Bitacora.objects.create(usuario=perfil, accion='Ingreso al sistema', descripcion=f'Usuario {user.email} inició sesión', ip_address=ip)
                except Exception:
                    pass
            except Usuario.DoesNotExist:
                perfil_serializado = None

            return Response({
                "token": token.key,
                "user": perfil_serializado
            })
        else:
            return Response(
                {"error": "Credenciales inválidas."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except User.DoesNotExist:
        return Response(
            {"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND
        )




@api_view(["POST"])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except Exception as exc:
        # DRF ValidationError will be returned as field-errors; keep format as dict of lists
        errs = {}
        if hasattr(exc, 'detail'):
            # exc.detail may be dict or list
            detail = exc.detail
            if isinstance(detail, dict):
                # ensure all values are lists of strings
                for k, v in detail.items():
                    if isinstance(v, list):
                        errs[k] = [str(x) for x in v]
                    else:
                        errs[k] = [str(v)]
            else:
                errs['non_field_errors'] = [str(detail)]
        else:
            errs['non_field_errors'] = [str(exc)]
        return Response(errs, status=status.HTTP_400_BAD_REQUEST)

    # create the perfil (RegisterSerializer.create returns Usuario profile)
    try:
        perfil = serializer.save()
    except serializers.ValidationError as ve:
        # create may raise field-specific errors (e.g., rol not found)
        detail = ve.detail if hasattr(ve, 'detail') else {'non_field_errors': [str(ve)]}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    # crear token y devolver el objeto público del usuario
    token, _ = Token.objects.get_or_create(user=perfil.user)

    public_user = PublicUsuarioSerializer(perfil).data
    # registrar en bitacora: registro de usuario
    ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
    try:
        Bitacora.objects.create(usuario=perfil, accion='Registro', descripcion=f'Usuario {perfil.user.email} registrado', ip_address=ip)
    except Exception:
        pass

    return Response({"token": token.key, "user": public_user}, status=status.HTTP_201_CREATED)





@api_view(["POST"])
def perfil(request):
    return Response({"message": "perfil successful"})


@api_view(["POST"])
def logout(request):
    # Invalida/elimina el token del usuario actual (si existe)
    token_key = None
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    # Accept both 'Token <key>' and 'Bearer <key>'
    if auth_header:
        if auth_header.startswith('Token ') or auth_header.startswith('Bearer '):
            token_key = auth_header.split(' ', 1)[1]

    # Also accept token in request body (some frontends may send it there)
    if not token_key:
        try:
            token_key = request.data.get('token')
        except Exception:
            token_key = None

    token_obj = None
    user = None
    if token_key:
        try:
            token_obj = Token.objects.get(key=token_key)
            user = getattr(token_obj, 'user', None)
        except Token.DoesNotExist:
            token_obj = None

    # If no token provided or invalid, fallback to request.user if session-authenticated
    if not user and getattr(request, 'user', None) and request.user.is_authenticated:
        user = request.user

    if not user:
        # nothing to logout / unknown token
        return Response(status=status.HTTP_400_BAD_REQUEST)

    # registrar en bitacora: logout (antes de eliminar el token si existe)
    ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
    try:
        perfil = getattr(user, 'perfil', None)
        Bitacora.objects.create(usuario=perfil, accion='Salida', descripcion=f'Usuario {getattr(user, "email", getattr(user, "username", "unknown"))} cerró sesión', ip_address=ip)
    except Exception:
        pass

    # eliminar el token si fue encontrado
    if token_obj:
        try:
            token_obj.delete()
        except Exception:
            pass

    return Response(status=status.HTTP_204_NO_CONTENT)
