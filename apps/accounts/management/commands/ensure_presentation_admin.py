import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or promote the presentation administrator from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "furnicore_admin").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@furnicore.local").strip()

        if not password:
            self.stdout.write("DJANGO_SUPERUSER_PASSWORD is not set; skipping admin bootstrap.")
            return
        if len(password) < 16:
            raise CommandError("DJANGO_SUPERUSER_PASSWORD must be at least 16 characters.")
        if not username:
            raise CommandError("DJANGO_SUPERUSER_USERNAME cannot be empty.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        if hasattr(user, "role"):
            user.role = "OWNER"
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Presentation administrator {action}: {username}"))
