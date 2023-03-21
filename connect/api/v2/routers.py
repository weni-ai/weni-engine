from django.urls import path, include
from rest_framework_nested import routers

from connect.api.v2.channels.views import ChannelsAPIView, CreateWACChannelAPIView, ListChannelsAPIView
from connect.api.v2.classifier.views import CreateClassifierAPIView, ListClassifierAPIView, RetrieveClassfierAPIView, DeleteClassifierAPIView
from connect.api.v2.ticketer.views import TicketerAPIView
from connect.api.v2.user.views import UserAPIToken


router = routers.SimpleRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("projects/<uuid:project_uuid>/create-classifier", CreateClassifierAPIView.as_view(), name="create-classifier"),
    path("projects/<uuid:project_uuid>/list-classifier", ListClassifierAPIView.as_view(), name="list-classifier"),
    path("projects/<uuid:project_uuid>/retrieve-classifier", RetrieveClassfierAPIView.as_view(), name="retrieve-classifier"),
    path("projects/<uuid:project_uuid>/delete-classifier", DeleteClassifierAPIView.as_view(), name="delete-classifier"),
    path("projects/<uuid:project_uuid>/ticketer", TicketerAPIView.as_view(), name="ticketer"),
    path("projects/<uuid:project_uuid>/channel", ChannelsAPIView.as_view(), name="channels"),
    path("projects/channels", ListChannelsAPIView.as_view(), name="list-channels"),
    path("projects/<uuid:project_uuid>/create-wac-channel", CreateWACChannelAPIView.as_view(), name="create-wac-channel"),
    path("projects/<uuid:project_uuid>/user-api-token", UserAPIToken.as_view(), name="user-api-token")
]
