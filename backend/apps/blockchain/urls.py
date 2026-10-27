from django.urls import path
from .views import DocumentProofView

urlpatterns = [
    path('blockchain/document/<uuid:document_reference>/', DocumentProofView.as_view(), name='public-document-blockchain-proof'),
]
