from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .serializers import AlertSerializer
from connect.usecases import alerts


class AlertViewSet(ModelViewSet):

    serializer_class = AlertSerializer

    def get_queryset(self):
        use_case = alerts.AlertListUseCase()

        return use_case.list_alerts(token=self.request.META.get("HTTP_AUTHORIZATION"))

    def retrieve(self, request, *args, **kwargs):
        use_case = alerts.AlertRetrieveUseCase()

        alert_uuid = kwargs.get("alert_uuid")
        alert = use_case.retrieve_alert(
            token=self.request.META.get("HTTP_AUTHORIZATION"),
            alert_uuid=alert_uuid,
        )
        serializer = AlertSerializer(alert)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        use_case = alerts.AlertCreateUseCase()

        serializer = AlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        can_be_closed = serializer.validated_data.get("can_be_closed")
        text = serializer.validated_data.get("text")
        type = serializer.validated_data.get("type")

        alert = use_case.create_alert(
            token=self.request.META.get("HTTP_AUTHORIZATION"),
            can_be_closed=can_be_closed,
            text=text,
            type=type,
        )

        return Response(AlertSerializer(alert).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        use_case = alerts.AlertUpdateUseCase()

        alert_uuid = kwargs.get("alert_uuid")
        update_alert = use_case.update_alert(
            token=self.request.META.get("HTTP_AUTHORIZATION"),
            alert_uuid=alert_uuid,
            can_be_closed=request.data.get("can_be_closed"),
            text=request.data.get("text"),
            type=request.data.get("type"),
        )

        return Response(AlertSerializer(update_alert).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        use_case = alerts.AlertDeleteUseCase()

        alert_uuid = kwargs.get("alert_uuid")
        use_case.delete_alert(
            token=self.request.META.get("HTTP_AUTHORIZATION"),
            alert_uuid=alert_uuid,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
