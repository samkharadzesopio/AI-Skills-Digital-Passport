from django.contrib.auth import login, logout
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET
from rest_framework.response import Response
from rest_framework.views import APIView

from .persistent_otp import consume_login_code, request_login_code


@require_GET
def csrf_token(request):
    return JsonResponse({'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class RequestLoginCode(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        message = request_login_code(
            request.data.get('email'), client_ip=request.META.get('REMOTE_ADDR', ''),
        )
        return Response({'detail': message}, status=202)


@method_decorator(csrf_protect, name='dispatch')
class VerifyLoginCode(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        with transaction.atomic():
            user = consume_login_code(
                request.data.get('email'), request.data.get('code'),
                client_ip=request.META.get('REMOTE_ADDR', ''),
            )
            if user is None:
                return Response({'detail': 'Invalid or expired login code.'}, status=400)
            # Rotate session key and CSRF token, then persist within the OTP transaction.
            login(request, user, backend='apps.accounts.authentication.StudentOTPBackend')
            request.session.save()
        return Response({'detail': 'Authenticated.'})


@method_decorator(csrf_protect, name='dispatch')
class Logout(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logout(request)
        return Response(status=204)
