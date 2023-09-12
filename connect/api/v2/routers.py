from django.urls import path, include
from rest_framework_nested import routers

from connect.api.v2.channels.views import ChannelsAPIView, CreateWACChannelAPIView, ListChannelsAPIView
from connect.api.v2.classifier.views import CreateClassifierAPIView, ListClassifierAPIView, RetrieveClassfierAPIView, DeleteClassifierAPIView
from connect.api.v2.ticketer.views import TicketerAPIView
from connect.api.v2.user.views import UserAPIToken, UserIsPaying
from connect.api.v2.omie.views import OmieAccountAPIView, OmieOriginAPIView, OmieSolutionsAPIView, OmieUsersAPIView

from connect.api.v2.template_projects.views import TemplateTypeViewSet, TemplateFeatureViewSet

from connect.api.v2.organizations import views as organization_views
from connect.api.v2.projects import views as project_views
from connect.api.v2.internals import views as connect_internal_views


router = routers.SimpleRouter()
router.register(r"projects/template-type", TemplateTypeViewSet, basename="template-type")
router.register(r"projects/template-features", TemplateFeatureViewSet, basename="template-features")

router.register(
    "organizations", organization_views.OrganizationViewSet, basename="organizations"
)

projects_router = routers.NestedSimpleRouter(
    router, r"organizations", lookup="organization"
)

projects_router.register(
    "projects", project_views.ProjectViewSet, basename="organization-projects"
)

urlpatterns = [
    path("", include(router.urls)),
    path("projects/<project_uuid>/create-classifier", CreateClassifierAPIView.as_view(), name="create-classifier"),
    path("projects/<project_uuid>/list-classifier", ListClassifierAPIView.as_view(), name="list-classifier"),
    path("projects/<project_uuid>/retrieve-classifier", RetrieveClassfierAPIView.as_view(), name="retrieve-classifier"),
    path("projects/<project_uuid>/delete-classifier", DeleteClassifierAPIView.as_view(), name="delete-classifier"),
    path("projects/<project_uuid>/ticketer", TicketerAPIView.as_view(), name="ticketer"),
    path("projects/<project_uuid>/channel", ChannelsAPIView.as_view(), name="channels"),
    path("projects/channels", ListChannelsAPIView.as_view(), name="list-channels"),
    path("projects/<project_uuid>/create-wac-channel", CreateWACChannelAPIView.as_view(), name="create-wac-channel"),
    path("projects/<project_uuid>/user-api-token", UserAPIToken.as_view(), name="user-api-token"),
    path("projects/<project_uuid>/user-api-token", UserAPIToken.as_view(), name="user-api-token"),
    path("account/user-is-paying", UserIsPaying.as_view(), name="user-is-paying"),
    path("omie/accounts", OmieAccountAPIView.as_view(), name="omie-accounts"),
    path("omie/origins", OmieOriginAPIView.as_view(), name="omie-origins"),
    path("omie/solutions", OmieSolutionsAPIView.as_view(), name="omie-solutions"),
    path("omie/users", OmieUsersAPIView.as_view(), name="omie-users"),
]
urlpatterns += [
    path("", include(projects_router.urls)),
    path(
        "internals/connect/organizations/",
        connect_internal_views.AIGetOrganizationView.as_view(),
    ),
    path("internals/connect/projects/<uuid>", connect_internal_views.InternalProjectViewSet.as_view({"patch": "partial_update"}))
]
