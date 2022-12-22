from django.urls import path, include
from .routers import router
from .channel_types.views import ChannelTypesAPIView
from .recent_activity.views import RecentActivityAPIView

urlpatterns = [
    path("", include(router.urls)),
    path("channel-types", ChannelTypesAPIView.as_view(), name="channel-types"),
    path("recent-activity", RecentActivityAPIView.as_view(), name="recent-activity")
]
