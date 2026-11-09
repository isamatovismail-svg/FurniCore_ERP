from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import Http404
from .models import User, AuditLog

def dev_login_view(request):
    """Convenient developer login for local development and automated testing (DEBUG mode only)."""
    if not settings.DEBUG:
        raise Http404("Available only in DEBUG mode")
    username = request.GET.get('user', 'owner')
    try:
        user = User.objects.get(username=username)
        login(request, user)
        next_url = request.GET.get('next', '/')
        return redirect(next_url)
    except User.DoesNotExist:
        return redirect('accounts:login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                AuditLog.objects.create(
                    user=user,
                    action='LOGIN',
                    entity_type='User',
                    entity_id=str(user.id),
                    details={'ip': request.META.get('REMOTE_ADDR')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, f'Добро пожаловать в FurniCore ERP, {user.first_name or user.username}!')
                next_url = request.GET.get('next') or request.POST.get('next') or '/'
                return redirect(next_url)
            else:
                messages.error(request, 'Ваша учетная запись деактивирована.')
        else:
            messages.error(request, 'Неверный логин или пароль.')

    return render(request, 'accounts/login.html')

def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='LOGOUT',
            entity_type='User',
            entity_id=str(request.user.id),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    logout(request)
    messages.info(request, 'Сессия завершена.')
    return redirect('accounts:login')

@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})
