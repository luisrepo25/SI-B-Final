from django.db import models

from core.models import TimeStampedModel
from django.contrib.auth.models import User

# Create your models here.


class Rol(TimeStampedModel):
    """Roles globales del sistema. Se añaden slug y descripción para identificar
    fácilmente desde el frontend.
    """
    slug = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class UserRole(TimeStampedModel):
    """Relación explícita usuario <-> rol para soportar múltiples roles por usuario
    y campos auditables (assigned_by, assigned_at).
    Se asocia a `django.contrib.auth.models.User` para interoperar con la API
    que trabaja con users por id.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='user_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_roles')

    class Meta:
        # Enforce a single UserRole row per user: cada usuario solo puede tener un rol
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_user_per_userrole'),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.rol.slug}"
