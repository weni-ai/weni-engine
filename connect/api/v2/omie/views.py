from rest_framework import views, status
from rest_framework.response import Response

from connect.api.clients.omie import OmieClient


class OmieAccountAPIView(views.APIView):

    def get(self, request):

        """ Returns omie account listing and detail """

        app_key = request.query_params.get("app_key")
        app_secret = request.query_params.get("app_secret")

        if not app_key or not app_secret:
            response_data = {"Invalid app_key or app_secret"}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)

        omie = OmieClient(app_key, app_secret)

        response = omie.list_accounts()
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            return_data = {"accounts": []}
            for cadastro in data.get("cadastros"):
                return_data["accounts"].append({
                    "cCodInt": cadastro.get("identificacao").get("cCodInt"),
                    "cNome": cadastro.get("identificacao").get("cNome"),
                })

            return Response(status=status.HTTP_200_OK, data=return_data)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": response.text})


class OmieOriginAPIView(views.APIView):
    def get(self, request):

        """ Returns omie origin listing and detail """

        app_key = request.query_params.get("app_key")
        app_secret = request.query_params.get("app_secret")

        if not app_key or not app_secret:
            response_data = {"Invalid app_key or app_secret"}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)

        omie = OmieClient(app_key, app_secret)

        response = omie.list_origins()

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            return_data = {"origins": []}

            for cadastro in data.get("cadastros"):
                return_data["origins"].append(cadastro)

            return Response(status=status.HTTP_200_OK, data=return_data)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": response.text})


class OmieSolutionsAPIView(views.APIView):
    def get(self, request):

        """ Returns omie solutions listing and detail """

        app_key = request.query_params.get("app_key")
        app_secret = request.query_params.get("app_secret")

        if not app_key or not app_secret:
            response_data = {"Invalid app_key or app_secret"}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)

        omie = OmieClient(app_key, app_secret)

        response = omie.list_solutions()

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            return_data = {"solutions": []}

            for cadastro in data.get("cadastros"):
                return_data["solutions"].append(cadastro)

            return Response(status=status.HTTP_200_OK, data=return_data)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": response.text})


class OmieUsersAPIView(views.APIView):
    def get(self, request):

        """ Returns omie users listing and detail """

        app_key = request.query_params.get("app_key")
        app_secret = request.query_params.get("app_secret")

        if not app_key or not app_secret:
            response_data = {"Invalid app_key or app_secret"}
            return Response(status=status.HTTP_400_BAD_REQUEST, data=response_data)

        omie = OmieClient(app_key, app_secret)

        response = omie.get_users()

        if response.status_code == status.HTTP_200_OK:
            data = response.json()

            return_data = {"users": []}

            for cadastro in data.get("listaUsuarios"):
                user = {
                    "cEmail": cadastro.get("cEmail"),
                    "cNome": cadastro.get("cNome"),
                    "nCodigo": cadastro.get("nCodigo"),
                }
                return_data["users"].append(user)

            return Response(status=status.HTTP_200_OK, data=return_data)

        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"message": response.text})
