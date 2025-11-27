# condominio/management/commands/generar_usuarios_ficticios.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from authz.models import Rol, UserRole          # Rol y UserRole están en authz
from condominio.models import Usuario           # 👈 ajusta si Usuario está en otra app


class Command(BaseCommand):
    help = "Genera usuarios Django ficticios, su perfil Usuario y les asigna el rol 'Cliente'."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cantidad',
            type=int,
            default=50,
            help='Cantidad de usuarios ficticios a generar (por defecto 50).',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='12345678',
            help='Password que se asignará a todos los usuarios generados.',
        )
        parser.add_argument(
            '--prefijo',
            type=str,
            default='cliente',
            help='Prefijo del username (ej: cliente -> cliente0001, cliente0002...).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        cantidad = options['cantidad']
        password = options['password']
        prefijo = options['prefijo']

        # 1) Aseguramos el rol "Cliente" buscando por nombre (que es único)
        rol_cliente, creado = Rol.objects.get_or_create(
            nombre='Cliente',   # nombre es unique en tu modelo
            defaults={
                'slug': 'cliente',
                'descripcion': 'Rol de cliente para reservas y compras.',
            }
        )

        # Si existía pero sin slug, lo actualizamos
        if not rol_cliente.slug:
            rol_cliente.slug = 'cliente'
            rol_cliente.save(update_fields=['slug'])
            self.stdout.write(self.style.WARNING(
                "ℹ️ Rol 'Cliente' existía sin slug, se actualizó slug='cliente'."
            ))
        elif creado:
            self.stdout.write(self.style.SUCCESS("✅ Rol 'Cliente' creado."))
        else:
            self.stdout.write(self.style.WARNING("ℹ️ Rol 'Cliente' ya existía."))

        creados = 0
        saltados = 0

        self.stdout.write(self.style.WARNING(
            f"🎯 Generando {cantidad} usuarios con prefijo '{prefijo}'..."
        ))

        for i in range(1, cantidad + 1):
            username = f"{prefijo}{i:04d}"  # cliente0001, cliente0002, etc.
            email = f"{username}@test.com"

            # Si el User ya existe, lo saltamos
            if User.objects.filter(username=username).exists():
                saltados += 1
                continue

            # 2) Crear User de Django
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            # 3) Crear perfil Usuario (OneToOne)
            #    Campos opcionales se dejan en blanco / null, num_viajes = 0 por defecto
            Usuario.objects.create(
                user=user,
                nombre=username,    # puedes cambiar a algo más bonito si quieres
                rol=rol_cliente,
                # rubro, telefono, etc. se quedan con sus valores por defecto (null/blank/0)
            )

            # 4) Crear o asegurar UserRole (único por user)
            user_role, ur_creado = UserRole.objects.get_or_create(
                user=user,
                defaults={
                    'rol': rol_cliente,
                    'assigned_by': None,
                }
            )
            # Si ya existía y tiene otro rol, lo actualizamos al rol_cliente
            if not ur_creado and user_role.rol != rol_cliente:
                user_role.rol = rol_cliente
                user_role.save(update_fields=['rol'])

            creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Usuarios nuevos creados: {creados}"
        ))
        if saltados:
            self.stdout.write(self.style.WARNING(
                f"⚠️ Usuarios saltados (ya existían con ese username): {saltados}"
            ))

        self.stdout.write(self.style.SUCCESS("🎉 Proceso de generación de usuarios finalizado."))
