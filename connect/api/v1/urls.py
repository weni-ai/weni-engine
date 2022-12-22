from django.urls import path, include
from .routers import router
from .recent_activity.views import RecentActivityAPIView

urlpatterns = [
    path("", include(router.urls)),
    path("recent-activity", RecentActivityAPIView.as_view(), name="recent-activity")
]
