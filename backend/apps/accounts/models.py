import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """Login identity; never use this UUID as a Student UUID."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    student = models.OneToOneField(
        'students.Student', null=True, blank=True, on_delete=models.PROTECT,
        related_name='login_account',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('email'), name='accounts_email_ci_unique'),
            models.CheckConstraint(
                condition=models.Q(student__isnull=True)
                | models.Q(is_staff=False, is_superuser=False),
                name='accounts_student_not_admin',
            ),
        ]


class LoginChallenge(models.Model):
    # HMAC of the normalized address; unknown identities receive buckets too.
    subject = models.CharField(max_length=64, primary_key=True)
    nonce = models.UUIDField(default=uuid.uuid4)
    code_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True)
    consumed_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_requested_at = models.DateTimeField(null=True)
    window_started_at = models.DateTimeField(null=True)
    request_count = models.PositiveIntegerField(default=0)


class LoginRateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
