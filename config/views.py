from django.http import JsonResponse
from django.db import connection


def health_check(request):
    """
    Production health check endpoint for load balancers (Nginx, AWS ALB, Traefik)
    and uptime monitoring. Verifies database connectivity and returns JSON.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
            row = cursor.fetchone()
            if not row or row[0] != 1:
                return JsonResponse(
                    {'status': 'unhealthy', 'database': 'error'},
                    status=503,
                )
    except Exception as err:
        return JsonResponse(
            {'status': 'unhealthy', 'database': 'disconnected', 'error': str(err)},
            status=503,
        )

    return JsonResponse(
        {'status': 'ok', 'database': 'connected', 'version': '1.0.0'},
        status=200,
    )
