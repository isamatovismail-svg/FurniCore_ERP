"""
FurniCore ERP — RBAC Decorators
Provides server-side enforcement for the DEMO_VIEWER role.
"""
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


_MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

_DEMO_BLOCKED_MSG = (
    'Демонстрационный просмотр: изменение данных недоступно в этом режиме.'
)


def deny_demo_viewer(view_func):
    """
    Decorator that blocks any state-mutating HTTP method (POST/PUT/PATCH/DELETE)
    for users with the DEMO_VIEWER role.

    GET requests are always allowed so the user can still view forms and pages.
    All other authenticated roles pass through unchanged.
    For HTMX or AJAX requests, returns HTTP 403 Forbidden.
    For standard browser requests, adds a warning message and redirects.

    Usage::

        @login_required
        @deny_demo_viewer
        def my_create_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if (
            request.method in _MUTATING_METHODS
            and getattr(request.user, 'is_demo_viewer', False)
        ):
            if (
                request.headers.get('HX-Request')
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'
            ):
                return HttpResponseForbidden(_DEMO_BLOCKED_MSG)

            messages.warning(request, _DEMO_BLOCKED_MSG)
            # Redirect back to the referring page; fall back to dashboard root.
            referer = request.META.get('HTTP_REFERER', '/')
            return redirect(referer)
        return view_func(request, *args, **kwargs)

    return _wrapped_view
