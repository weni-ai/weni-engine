from django.urls import path, include

from .routers import router
from .channel_types.views import ChannelTypesAPIView
from .recent_activity.views import RecentActivityAPIView, RecentActivityListAPIView
from .externals.urls import urlpatterns as externals_urls


urlpatterns = [
    path("", include(router.urls)),
    path("channel-types", ChannelTypesAPIView.as_view(), name="channel-types"),
    path("recent-activity", RecentActivityAPIView.as_view(), name="recent-activity"),
    path(
        "recent-activities",
        RecentActivityListAPIView.as_view(),
        name="recent-activity-list",
    ),
]

urlpatterns += externals_urls
