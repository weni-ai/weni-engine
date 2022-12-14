from django.urls import path, include
from .routers import router
from .channel_types.views import ChannelTypesAPIView


urlpatterns = [
    path("", include(router.urls)),
    path("channel-types", ChannelTypesAPIView.as_view(), name="channel-types"),
]
