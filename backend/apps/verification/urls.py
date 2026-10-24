
from django.urls import path

from .views import (
    CredentialVerificationView,
    DocumentVerificationView,
)


urlpatterns = [
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
