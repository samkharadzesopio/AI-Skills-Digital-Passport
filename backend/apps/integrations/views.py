
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from .serializers import ClassroomCompletionSerializer
from .services import ClassroomService


class ClassroomCompletionsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        service = ClassroomService()
        records = service.get_completions()

        serializer = ClassroomCompletionSerializer(
            records,
            many=True
        )

        return Response({
            "source": "SIMULATED_BTU_CLASSROOM",
            "count": len(records),
            "results": serializer.data
        })


class ClassroomSyncView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        service = ClassroomService()
        eligible = service.get_eligible_completions()

        if request.data.get("dry_run") is not True:
            return Response(
                {
                    "status": "not_configured",
                    "detail": (
                        "Live synchronization requires "
                        "credential issuance and a durable ledger."
                    ),
                },
                status=503,
            )

        return Response({
            "status": "preview",
            "source": "SIMULATED_BTU_CLASSROOM",
            "eligible_count": len(eligible),
            "eligible_event_ids": [
                record["event_id"] for record in eligible
            ],
            "credentials_issued": 0,
        })
