from collections.abc import Mapping

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET
from rest_framework.exceptions import ParseError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.students.models import Student

from .otp_store import AuthRateLimitExceeded
from .persistent_otp import consume_login_code, request_login_code
from .permissions import IsAdminWithPermission
from .serializers import (
    EmailInputSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    RegistrationSerializer,
    StudentInvitationSerializer,
)
from .services import (
    EmailDeliveryUnavailable,
    InvalidInvitation,
    InvalidRecoveryCode,
    check_login_rate_limit,
    create_student_account_invitation,
    redeem_student_account_invitation,
    request_password_reset,
    reset_password_with_otp,
    revoke_student_account_invitation,
    send_email_verification_code,
    send_invitation_email,
    verify_email_code,
)


def login_payload(request):
    data = request.data
    if not isinstance(data, Mapping):
        raise ParseError('Expected a JSON object or form fields.')
    return data


@require_GET
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


csrf_token = ensure_csrf_cookie(csrf_token)


@method_decorator(csrf_protect, name="dispatch")
class OTPLoginRequestView(APIView):
    """Request a persistent OTP for an eligible student mailbox."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = login_payload(request)
        message = request_login_code(
            data.get('email'), client_ip=request.META.get('REMOTE_ADDR', ''),
        )
        return Response({"detail": message}, status=status.HTTP_202_ACCEPTED)


@method_decorator(csrf_protect, name="dispatch")
class OTPLoginVerifyView(APIView):
    """Consume a student OTP and persist a rotated session atomically."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = login_payload(request)
        with transaction.atomic():
            user = consume_login_code(
                data.get('email'), data.get('code'),
                client_ip=request.META.get('REMOTE_ADDR', ''),
            )
            if user is None:
                return Response(
                    {"detail": "Invalid or expired login code."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            login(request, user, backend="apps.accounts.authentication.StudentOTPBackend")
            request.session.save()
        return Response({"detail": "Authenticated."}, status=status.HTTP_200_OK)


def _user_summary(user):
    linked = bool(
        user
        and getattr(user, "role", None) == "STUDENT"
        and getattr(user, "student_id", None)
    )
    return {
        "email": user.email,
        "role": user.role,
        "email_verified": user.is_email_verified,
        "student_association": "linked" if linked else "unlinked",
    }


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        try:
            check_login_rate_limit(email, request.META.get("REMOTE_ADDR"))
        except AuthRateLimitExceeded:
            return Response(
                {"detail": "Too many login attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = authenticate(request, email=email, password=password)
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response(_user_summary(user), status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_active:
            raise PermissionDenied("Authentication required.")
        return Response(_user_summary(request.user))


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = redeem_student_account_invitation(
                token=serializer.validated_data["invitation_token"],
                password=serializer.validated_data["password"],
            )
        except InvalidInvitation:
            return Response(
                {"detail": "Invitation is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            return Response({"new_password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_user_summary(user), status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response(
                {"current_password": ["Current password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        return Response({"status": "password_changed"})


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            request_password_reset(
                email=serializer.validated_data["email"],
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except AuthRateLimitExceeded:
            pass
        except ValueError:
            pass
        return Response(
            {"detail": "If the account is eligible, a recovery code will be sent."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reset_password_with_otp(**serializer.validated_data)
        except InvalidRecoveryCode:
            return Response(
                {"detail": "Recovery request is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            return Response({"new_password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "password_reset"})


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            send_email_verification_code(
                user=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except AuthRateLimitExceeded:
            pass
        except EmailDeliveryUnavailable:
            return Response(
                {"detail": "Verification delivery is unavailable. Retry later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {"detail": "If verification is required, a code will be sent."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class EmailVerificationConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code")
        if not verify_email_code(user=request.user, code=code):
            return Response(
                {"detail": "Verification code is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"email_verified": True})


@method_decorator(csrf_protect, name="dispatch")
class StudentInvitationCreateView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.manage_student_accounts"

    def post(self, request):
        serializer = StudentInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation, token, email = create_student_account_invitation(
                student_id=serializer.validated_data["student_id"],
                actor=request.user,
            )
        except PermissionDenied:
            raise
        except InvalidInvitation:
            return Response(
                {"detail": "Account invitation cannot be created."},
                status=status.HTTP_409_CONFLICT,
            )
        except Student.DoesNotExist:
            return Response({"detail": "Student record not found."}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, ValueError):
            return Response(
                {"detail": "Student record is not eligible for account provisioning."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            send_invitation_email(email=email, token=token)
        except Exception:
            revoke_student_account_invitation(invitation.pk)
            return Response(
                {"detail": "Invitation delivery failed. Retry later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "invitation_sent"}, status=status.HTTP_202_ACCEPTED)


class StudentAccountStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_summary(request.user))
