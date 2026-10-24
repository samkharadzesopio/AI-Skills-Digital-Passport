
from django.urls import path
from .views import CredentialVerificationView


urlpatterns = [
    path(
        "<str:credential_id>/",
        CredentialVerificationView.as_view(),
        name="credential-verification",
    ),
]
