web: python sync_migrations.py && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application
