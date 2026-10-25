from django.urls import path

from .views import (
    CurrentUserView,
    EmailVerificationConfirmView,
    EmailVerificationRequestView,
    LoginView,
    LogoutView,
    OTPLoginRequestView,
    OTPLoginVerifyView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    StudentAccountStatusView,
    StudentInvitationCreateView,
    csrf_token,
)

app_name = "accounts"

urlpatterns = [
    path("csrf/", csrf_token, name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("otp/request/", OTPLoginRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPLoginVerifyView.as_view(), name="otp-verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("student-status/", StudentAccountStatusView.as_view(), name="student-status"),
    path("register/", RegisterView.as_view(), name="register"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("email/verify/request/", EmailVerificationRequestView.as_view(), name="email-verification-request"),
    path("email/verify/confirm/", EmailVerificationConfirmView.as_view(), name="email-verification-confirm"),
    path("admin/student-invitations/", StudentInvitationCreateView.as_view(), name="student-invitation-create"),
]
