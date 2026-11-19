"""
setup_teacher_account.py — Safely create or update a dedicated demonstration account for the teacher.

Security Guarantees:
- Never grants superuser (is_superuser=False).
- Never grants staff access to /admin/ (is_staff=False).
- Grants evaluator/manager access to inspect all functional ERP modules.
- Does not expose passwords in code or Git.
"""
import getpass
import secrets
import string
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import UserRole


class Command(BaseCommand):
    help = 'Создаёт или обновляет безопасную демонстрационную учётную запись преподавателя (без прав суперпользователя и /admin/).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='teacher',
            help='Имя пользователя (по умолчанию: teacher)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Пароль (если не указан, будет сгенерирован или запрошен интерактивно)',
        )
        parser.add_argument(
            '--role',
            type=str,
            default=UserRole.DEMO_VIEWER,
            help='Роль учётной записи (по умолчанию: DEMO_VIEWER)',
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Интерактивный ввод пароля через консоль',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username'].strip()
        raw_password = options.get('password')

        if options.get('interactive'):
            raw_password = getpass.getpass('Введите пароль для преподавателя: ')
            confirm = getpass.getpass('Подтвердите пароль: ')
            if raw_password != confirm:
                self.stderr.write(self.style.ERROR('Пароли не совпадают!'))
                return
        elif not raw_password:
            # Generate a secure 10-character demonstration passphrase
            alphabet = string.ascii_letters + string.digits
            raw_password = 'Demo-' + ''.join(secrets.choice(alphabet) for _ in range(8))

        role = options.get('role', UserRole.DEMO_VIEWER)
        if role not in UserRole.values:
            self.stderr.write(self.style.ERROR(f'Недопустимая роль: {role}. Доступные: {UserRole.values}'))
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': 'Преподаватель',
                'last_name': 'Оценщик',
                'email': f'{username}@furnicore.demo',
                'role': role,
                'is_staff': False,      # Strictly NO /admin/ access
                'is_superuser': False,  # Strictly NO superuser access
                'is_active': True,
            }
        )

        user.set_password(raw_password)
        user.role = role
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.save()

        action_str = 'создана' if created else 'обновлена'
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Демонстрационная учётная запись преподавателя успешно {action_str}!\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'• Логин:     {username}\n'
            f'• Пароль:    {raw_password}\n'
            f'• Роль:      {user.get_role_display()} ({role})\n'
            f'• Режим:     Безопасный демонстрационный просмотр (Read-Only)\n'
            f'• Доступ к /admin/:  ЗАБЛОКИРОВАН (is_staff=False)\n'
            f'• Права суперпользователя:  НЕТ (is_superuser=False)\n'
            f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
            f'⚠ Сохраните пароль для передачи преподавателю.\n'
        ))
