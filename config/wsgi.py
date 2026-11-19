import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Standalone WSGI static file serving (for demo Gunicorn / Cloudflare Tunnel without Nginx)
if os.getenv('SERVE_STATIC', 'False').lower() in ('true', '1', 'yes'):
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    application = StaticFilesHandler(application)
