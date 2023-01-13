from django.urls import path, include
from rest_framework_nested import routers

from connect.api.v2.channels.views import ChannelsAPIView, CreateWACChannelAPIView
from connect.api.v2.classifier.views import CreateClassifierAPIView, ListClassifierAPIView, RetrieveClassfierAPIView, DeleteClassifierAPIView
from connect.api.v2.ticketer.views import TicketerAPIView

# from connect.api.v2.organizations import views as organization_views
# from connect.api.v2.projects import views as project_views
# from connect.api.v2.plans import views as plan_views

router = routers.SimpleRouter()

# router.register('organizations', organization_views.OrganizationViewSet, basename="organizations")

# projects_router = routers.NestedSimpleRouter(router, r"organizations", lookup="organization")
# projects_router.register('projects', project_views.ProjectViewSet, basename="organization-projects")

# plans_router = routers.NestedSimpleRouter(router, r"organizations", lookup="plan")
# plans_router.register('plans', plan_views.PlanViewSet, basename="organization-plans")

urlpatterns = [
    path("", include(router.urls)),
    path("create-classifier", CreateClassifierAPIView.as_view(), name="create-classifier"),
    path("list-classifier", ListClassifierAPIView.as_view(), name="list-classifier"),
    path("retrieve-classifier", RetrieveClassfierAPIView.as_view(), name="retrieve-classifier"),
    path("delete-classifier", DeleteClassifierAPIView.as_view(), name="delete-classifier"),
    path("ticketer", TicketerAPIView.as_view(), name="ticketer"),
    path("channel", ChannelsAPIView.as_view(), name="channels"),
    path("create-wac-channel", CreateWACChannelAPIView.as_view(), name="create-wac-channel")
    #     path("", include(projects_router.urls)),
    #     path("", include(plans_router.urls)),
]
