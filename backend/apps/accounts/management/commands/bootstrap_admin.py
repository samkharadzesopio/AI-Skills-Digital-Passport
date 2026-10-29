from getpass import getpass

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.managers import normalize_login_email
from apps.accounts.models import ADMIN_PERMISSION_CODENAMES, User


class Command(BaseCommand):
    help = "Create the first least-privilege BTU administrator account."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--permissions", nargs="+", required=True)

    def handle(self, *args, **options):
        try:
            email = normalize_login_email(options["email"])
        except (TypeError, ValueError) as exc:
            raise CommandError("A valid administrator email is required.") from exc
        permissions = set(options["permissions"])
        if not permissions or not permissions.issubset(ADMIN_PERMISSION_CODENAMES):
            raise CommandError("Select only approved accounts permission codenames.")
        existing_admins = User.objects.filter(
            role=User.Role.ADMIN,
            is_active=True,
            is_superuser=False,
        ).prefetch_related("user_permissions", "groups__permissions")
        if any(user.has_perm("accounts.access_admin_api") for user in existing_admins):
            raise CommandError("An active API administrator already exists.")
        password = getpass("Administrator password: ")
        confirmation = getpass("Confirm password: ")
        if not password or password != confirmation:
            raise CommandError("Passwords did not match.")
        with transaction.atomic():
            try:
                user = User.objects.create_admin_user(
                    email=email,
                    password=password,
                    permission_codenames=permissions,
                )
            except Exception as exc:
                raise CommandError("Administrator account could not be created.") from exc
        self.stdout.write(self.style.SUCCESS(f"Created administrator account {user.pk}."))
