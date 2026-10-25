
from django.urls import path

from .views import (
    CredentialVerificationView,
    PassportVerificationView,
    PassportVersionVerificationView,
    DocumentVerificationView,
)


urlpatterns = [
    path('passport/<str:verification_reference>/', PassportVerificationView.as_view(), name='passport-verification'),
    path('passport-version/<str:verification_reference>/', PassportVersionVerificationView.as_view(), name='passport-version-verification'),
    path(
        "document/",
        DocumentVerificationView.as_view(),
        name="document-verification",
    ),
    path(
        "<str:credential_id>/",
        CredentialVerificationView.as_view(),
        name="credential-verification",
    ),
]
