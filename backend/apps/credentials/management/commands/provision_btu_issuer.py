from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.credentials.models import BTU_ISSUER_DISPLAY_NAME
from apps.credentials.services import provision_btu_issuer


class Command(BaseCommand):
    help = "Provision the fixed trusted BTU credential issuer for an authorized administrator."

    def add_arguments(self, parser):
        parser.add_argument("--actor-email", required=True)
        parser.add_argument("--display-name", default=BTU_ISSUER_DISPLAY_NAME)

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(email__iexact=options["actor_email"].strip())
        except get_user_model().DoesNotExist:
            raise CommandError("The specified administrator account does not exist.") from None
        try:
            issuer, changed = provision_btu_issuer(
                actor=actor,
                display_name=options["display_name"],
            )
        except (PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from None
        state = "provisioned" if changed else "already configured"
        self.stdout.write(self.style.SUCCESS(f"BTU issuer {state}: {issuer.reference}"))
