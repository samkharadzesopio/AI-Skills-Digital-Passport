from django.contrib.auth import login
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .audit import AuditedAPIView
from .google_auth import GoogleProblem, begin, finish
from .otp_store import AuthRateLimitExceeded
from .views import _user_summary


@method_decorator(csrf_protect, name='dispatch')
class GoogleView(AuditedAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            if not isinstance(data, dict):
                raise GoogleProblem('GOOGLE_INVALID_REQUEST')
            if self.challenge:
                if set(data) != {'intent'}:
                    raise GoogleProblem('GOOGLE_INVALID_REQUEST')
                return Response(begin(request, data['intent']))
            if set(data) != {'challenge_id', 'credential'}:
                raise GoogleProblem('GOOGLE_INVALID_REQUEST')
            user, intent = finish(request, data['challenge_id'], data['credential'])
            if intent == 'login':
                login(request, user, backend='apps.accounts.authentication.GoogleWorkspaceBackend')
                request.session.pop('google_link_otp', None)
                request.session.save()
            return Response({'account': _user_summary(user), 'linked': intent == 'link'})
        except GoogleProblem as error:
            return Response({'code': error.code}, status=error.status)
        except AuthRateLimitExceeded:
            return Response({'code': 'GOOGLE_RATE_LIMITED'}, status=429, headers={'Retry-After': '900'})


class GoogleChallengeView(GoogleView):
    challenge = True


class GoogleAuthenticateView(GoogleView):
    challenge = False


class PortalSummaryView(AuditedAPIView):
    def get(self, request):
        from .portal import workspace_user, owned_student_id
        user = workspace_user(request.user)
        student_id = owned_student_id(user)
        return Response({'email': user.email, 'records_linked': student_id is not None,
            'mapping_pending': student_id is None})
