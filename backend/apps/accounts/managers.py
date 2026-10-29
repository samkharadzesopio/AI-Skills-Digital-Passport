from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models, transaction


def normalize_login_email(email):
    if not isinstance(email, str):
        raise ValueError("A valid email is required.")
    email = email.strip().lower()
    validate_email(email)
    return email


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email=normalize_login_email(username), portal_only=False)

    def create_user(self, email, password=None, **extra_fields):
        if extra_fields.get('portal_only'):
            raise ValueError('Portal principals are created only by verified Google authentication.')
        if not email:
            raise ValueError("Email is required.")
        # Preserve a legacy handle when a trusted internal caller supplies one;
        # new accounts remain email-only and do not need a second identifier.
        username = extra_fields.pop("username", None)
        if password is not None and (
            not isinstance(password, str) or not password or len(password) > 256
        ):
            raise ValueError("A password must be between 1 and 256 characters.")
        role = extra_fields.pop("role", "STUDENT")
        if role != "STUDENT":
            raise ValueError("Administrator accounts use the trusted admin provisioning workflow.")
        if extra_fields.get("is_staff") or extra_fields.get("is_superuser"):
            raise ValueError("Public student account creation cannot set staff privileges.")
        from .otp_utils import normalize_btu_email

        email = normalize_btu_email(normalize_login_email(email))
        user = self.model(
            email=normalize_login_email(email), role=role, username=username, **extra_fields
        )
        if password is None:
            user.set_unusable_password()
        else:
            validate_password(password, user=user)
            user.set_password(password)
        user.full_clean(exclude={"password", "last_login"})
        user.save(using=self._db)
        return user

    @transaction.atomic
    def create_admin_user(self, *, email, password, permission_codenames):
        from django.contrib.auth.models import Permission

        from .models import ADMIN_PERMISSION_CODENAMES, User

        requested = set(permission_codenames)
        if not requested or not requested.issubset(ADMIN_PERMISSION_CODENAMES):
            raise ValueError("Administrator permissions must be selected from the approved set.")
        if not isinstance(password, str) or not password or len(password) > 256:
            raise ValueError("A password between 1 and 256 characters is required.")
        from .otp_utils import normalize_btu_email

        normalized_email = normalize_btu_email(normalize_login_email(email))
        user = User(
            email=normalized_email,
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=False,
            is_email_verified=True,
        )
        validate_password(password, user=user)
        user.set_password(password)
        user.full_clean(exclude={"password", "last_login"})
        user.save(using=self._db)
        permissions = list(
            Permission.objects.filter(
                content_type__app_label="accounts",
                codename__in=requested,
            )
        )
        if {permission.codename for permission in permissions} != requested:
            raise ValidationError("One or more administrator permissions are unavailable.")
        user.user_permissions.set(permissions)
        return user

    def create_superuser(self, *args, **kwargs):
        raise ValueError("Superuser accounts are disabled; provision a least-privilege administrator.")
