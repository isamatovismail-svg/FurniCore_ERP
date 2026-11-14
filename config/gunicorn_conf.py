# ==============================================================================
# FurniCore ERP — Gunicorn Production Configuration
# ==============================================================================
import multiprocessing
import os

# Server Socket
bind = os.getenv('GUNICORN_BIND', '127.0.0.1:8000')
backlog = 2048

# Worker Processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gthread'
threads = int(os.getenv('GUNICORN_THREADS', 2))
worker_connections = 1000
timeout = int(os.getenv('GUNICORN_TIMEOUT', 60))
keepalive = 5

# Memory Management (recycle workers periodically to avoid leaks)
max_requests = 1000
max_requests_jitter = 50

# Server Mechanics
daemon = False
pidfile = os.getenv('GUNICORN_PIDFILE', None)
user = None
group = None
umask = 0
tmp_upload_dir = None

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" (%(D)s µs)'

# Process Naming
proc_name = 'furnicore_erp'

# Preload application code before worker processes are forked
preload_app = True


def on_starting(server):
    server.log.info("Starting FurniCore ERP Gunicorn Server...")


def on_exit(server):
    server.log.info("Shutting down FurniCore ERP Gunicorn Server.")
