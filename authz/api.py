from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.permissions import BasePermission
from rest_framework.pagination import PageNumberPagination

from authz.models import Rol, UserRole
from authz.serializer import RolSerializer
from django.contrib.auth.models import User
from condominio.models import Bitacora, Usuario
from authz.serializer import MeSerializer

from django.contrib.auth.models import User
from authz.serializer import UserWithRolesSerializer


class IsAdminOrHasChangeUser(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        return request.user.has_perm('auth.change_user') or request.user.is_staff


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class UsersListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrHasChangeUser]

    def get(self, request):
        q = request.GET.get('search')
        role = request.GET.get('role')
        users = User.objects.all().order_by('id')
        if q:
            users = users.filter(email__icontains=q) | users.filter(first_name__icontains=q) | users.filter(last_name__icontains=q)
        if role:
            users = users.filter(user_roles__rol__slug=role)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(users, request)
        serializer = UserWithRolesSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrHasChangeUser]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        # If a Usuario profile exists, return the profile representation (same shape as /api/users/me/)
        try:
            perfil = getattr(user, 'perfil', None)
            if perfil:
                serializer = MeSerializer(perfil)
                return Response(serializer.data)
            else:
                # fallback to previous user-only serializer
                serializer = UserWithRolesSerializer(user)
                return Response(serializer.data)
        except Usuario.DoesNotExist:
            # fallback to previous user-only serializer
            serializer = UserWithRolesSerializer(user)
            return Response(serializer.data)

    def patch(self, request, pk):
        # Allow admins (or users with change permission) to partially update another user's profile
        user = get_object_or_404(User, pk=pk)
        try:
            perfil = getattr(user, 'perfil', None)
            if not perfil:
                # create perfil if missing
                perfil = Usuario.objects.create(user=user)
        except Usuario.DoesNotExist:
            # create perfil if missing
            perfil = Usuario.objects.create(user=user)
        serializer = MeSerializer(perfil, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def put(self, request, pk):
        # Accept PUT from older frontends; treat as partial update for compatibility
        return self.patch(request, pk)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            perfil = getattr(request.user, 'perfil', None)
            if not perfil:
                return Response(status=404)
        except Usuario.DoesNotExist:
            return Response(status=404)
        serializer = MeSerializer(perfil)
        return Response(serializer.data)

    def patch(self, request):
        try:
            perfil = getattr(request.user, 'perfil', None)
            if not perfil:
                return Response(status=404)
        except Usuario.DoesNotExist:
            return Response(status=404)
        serializer = MeSerializer(perfil, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rol.objects.all().order_by('nombre')
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated]


class UserRolesView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        # idempotent update: add/remove lists
        user = get_object_or_404(User, pk=pk)
        add = request.data.get('add', [])
        remove = request.data.get('remove', [])
        # resolve role slugs/ids
        def resolve_role(r):
            if isinstance(r, int):
                return get_object_or_404(Rol, pk=r)
            return get_object_or_404(Rol, slug=r)

        with transaction.atomic():
            # Antes: obtener el rol actual (si existe)
            before = list(UserRole.objects.filter(user=user).values_list('rol__slug', flat=True))
            added = []
            removed = []

            # If add contains multiple roles, enforce single-role policy: only the last provided will be assigned.
            if isinstance(add, list) and len(add) > 1:
                # normalize to last role only
                add = [add[-1]]

            # Process removals first
            for r in remove:
                role = resolve_role(r)
                deleted, _ = UserRole.objects.filter(user=user, rol=role).delete()
                if deleted:
                    removed.append(role.slug)

            # If there's an add, remove any existing role(s) to enforce single-role constraint, then create the new one
            for r in add:
                role = resolve_role(r)
                # delete existing roles for user (should be at most one after migration)
                UserRole.objects.filter(user=user).exclude(rol=role).delete()
                ur, created = UserRole.objects.get_or_create(user=user, rol=role, defaults={'assigned_by': request.user})
                if created:
                    added.append(role.slug)

                # Sync Usuario.rol FK for convenience
                try:
                    perfil = getattr(user, 'perfil', None)
                    if perfil:
                        perfil.rol = role
                        perfil.save()
                except Exception:
                    pass

            after = list(UserRole.objects.filter(user=user).values_list('rol__slug', flat=True))
            # log bitacora
            try:
                perfil = getattr(user, 'perfil', None)
                Bitacora.objects.create(usuario=perfil, accion='UPDATE_ROLES', descripcion=f'Roles actualizados (added={added} removed={removed})', ip_address=request.META.get('REMOTE_ADDR'))
            except Exception:
                pass
        return Response({'id': user.pk, 'roles': after})

    def post(self, request, pk):
        # add single role
        user = get_object_or_404(User, pk=pk)
        role_payload = request.data.get('role')
        role = None
        if isinstance(role_payload, int):
            role = get_object_or_404(Rol, pk=role_payload)
        else:
            role = get_object_or_404(Rol, slug=role_payload)
        # Enforce single-role: remove other roles and assign this one
        with transaction.atomic():
            UserRole.objects.filter(user=user).exclude(rol=role).delete()
            ur, created = UserRole.objects.get_or_create(user=user, rol=role, defaults={'assigned_by': request.user})
            try:
                perfil = getattr(user, 'perfil', None)
                if perfil:
                    perfil.rol = role
                    perfil.save()
            except Exception:
                pass
            if created:
                try:
                    perfil = getattr(user, 'perfil', None)
                    Bitacora.objects.create(usuario=perfil, accion='ASSIGN_ROLE', descripcion=f'Rol {role.slug} asignado', ip_address=request.META.get('REMOTE_ADDR'))
                except Exception:
                    pass
                return Response({'id': user.pk, 'role': role.slug}, status=status.HTTP_201_CREATED)
        return Response({'id': user.pk, 'role': role.slug}, status=status.HTTP_200_OK)

    def delete(self, request, pk, role_slug=None):
        user = get_object_or_404(User, pk=pk)
        # role_slug can be slug or id
        try:
            if role_slug and role_slug.isdigit():
                role = get_object_or_404(Rol, pk=int(role_slug))
            else:
                role = get_object_or_404(Rol, slug=role_slug)
        except Exception:
            return Response(status=status.HTTP_404_NOT_FOUND)
        deleted, _ = UserRole.objects.filter(user=user, rol=role).delete()
        if deleted:
            try:
                perfil = getattr(user, 'perfil', None)
                Bitacora.objects.create(usuario=perfil, accion='REMOVE_ROLE', descripcion=f'Rol {role.slug} removido', ip_address=request.META.get('REMOTE_ADDR'))
            except Exception:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class SetUserActiveView(APIView):
    permission_classes = [IsAuthenticated,]

    def patch(self, request, pk):
        # Permitir solo admins o usuarios con auth.change_user
        if not (request.user.is_superuser or request.user.has_perm('auth.change_user') or request.user.is_staff):
            return Response({'detail': 'No autorizado'}, status=403)
        user = get_object_or_404(User, pk=pk)
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response({'detail': 'is_active required'}, status=400)
        user.is_active = bool(is_active)
        user.save()
        # revoke tokens if being disabled
        if not user.is_active:
            try:
                from rest_framework.authtoken.models import Token
                Token.objects.filter(user=user).delete()
            except Exception:
                pass
        # log bitacora
        try:
            perfil = getattr(user, 'perfil', None)
            accion = 'HABILITAR_USUARIO' if user.is_active else 'INACTIVAR_USUARIO'
            Bitacora.objects.create(usuario=perfil, accion=accion, descripcion=f'Usuario {user.email} {"habilitado" if user.is_active else "inhabilitado"} por {request.user.email}', ip_address=request.META.get('REMOTE_ADDR'))
        except Exception:
            pass
        return Response({'id': user.pk, 'is_active': user.is_active})
