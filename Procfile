release: python manage.py migrate --noinput && python manage.py createcachetable && python manage.py collectstatic --noinput
web: gunicorn stockapp.wsgi --workers ${WEB_WORKERS:-1} --threads ${WEB_THREADS:-8} --worker-class gthread --timeout 90 --log-file -
