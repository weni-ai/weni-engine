from rest_framework import views, status
from rest_framework.response import Response
from connect.api.v2.auth.serializers import KeycloakAuthSerializer
from connect.usecases.keycloak.authenticate import KeycloakAuthenticateUseCase


class KeycloakAuthView(views.APIView):
    def post(self, request):
        serializer = KeycloakAuthSerializer(data=request.data)
        if not serializer.is_valid(raise_exception=True):
            return Response(
                {"error": "Invalid input data"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            use_case = KeycloakAuthenticateUseCase()
            tokens = use_case.execute(
                username=serializer.validated_data["user"],
                password=serializer.validated_data["password"],
            )
            return Response(tokens, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
