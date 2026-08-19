from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from connect.usecases.currencies.list_currencies import ListCurrenciesUseCase


class CurrenciesView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"currencies": ListCurrenciesUseCase().execute()})
