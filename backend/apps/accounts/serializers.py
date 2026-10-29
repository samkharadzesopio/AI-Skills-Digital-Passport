from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .managers import normalize_login_email


class EmailInputSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        try:
            return normalize_login_email(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Enter a valid email address.") from None


class LoginSerializer(EmailInputSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)


class RegistrationSerializer(serializers.Serializer):
    invitation_token = serializers.CharField(write_only=True, trim_whitespace=True, max_length=128)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context.get("user"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None
        return value


class PasswordResetConfirmSerializer(EmailInputSerializer):
    code = serializers.CharField(write_only=True, trim_whitespace=True, max_length=32)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=256)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None
        return value


class StudentInvitationSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
