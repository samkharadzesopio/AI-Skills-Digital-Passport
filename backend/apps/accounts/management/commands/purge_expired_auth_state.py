from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import (
    AuthRateLimitBucket,
    LoginChallenge,
    LoginRateBucket,
    OTPChallenge,
)


class Command(BaseCommand):
    help = "Remove expired OTP challenges and inactive authentication rate-limit buckets."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=1)
        deleted_challenges, _ = OTPChallenge.objects.filter(
            expires_at__lt=cutoff
        ).delete()
        deleted_login_challenges, _ = LoginChallenge.objects.filter(
            expires_at__lt=cutoff
        ).delete()
        deleted_buckets, _ = AuthRateLimitBucket.objects.filter(
            window_started_at__lt=cutoff
        ).delete()
        deleted_login_buckets, _ = LoginRateBucket.objects.filter(
            window_started_at__lt=cutoff
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {deleted_challenges + deleted_login_challenges} expired challenges and "
                f"{deleted_buckets + deleted_login_buckets} stale rate-limit buckets."
            )
        )
