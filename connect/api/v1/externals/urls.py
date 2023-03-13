from django.urls import path

from .views import ExternalServiceAPIView


urlpatterns = [
    path("externals", ExternalServiceAPIView.as_view(), name='v1.externals'),
]
