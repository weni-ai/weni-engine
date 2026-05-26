"""Internal endpoint to dispatch the business verification result email."""

from rest_framework import status, views
from rest_framework.response import Response

from connect.api.v1.internal.permissions import ModuleHasPermission
from connect.usecases.business_verification.notify_business_verification import (
    NotifyBusinessVerificationUseCase,
)

from .serializers import NotifyBusinessVerificationSerializer


class NotifyBusinessVerificationView(views.APIView):
    """POST /v2/internals/business-verification/notify/

    Consumed by the integrations-engine after it receives the
    Partner-Led Business Verification webhook from Meta.
    """

    permission_classes = [ModuleHasPermission]

    def post(self, request):
        serializer = NotifyBusinessVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sent = NotifyBusinessVerificationUseCase().execute(
            user_email=serializer.validated_data["user_email"],
            status=serializer.validated_data["status"],
            rejection_reasons=serializer.validated_data["rejection_reasons"],
            verification_attempts=serializer.validated_data["verification_attempts"],
            language=serializer.validated_data["language"],
        )

        return Response({"sent": bool(sent)}, status=status.HTTP_200_OK)
