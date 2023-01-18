from django.urls import path, include
from rest_framework_nested import routers

from connect.api.v2.organizations import views as organization_views
from connect.api.v2.projects import views as project_views

router = routers.SimpleRouter()
router.register('organizations', organization_views.OrganizationViewSet, basename="organizations")

projects_router = routers.NestedSimpleRouter(router, r"organizations", lookup="organization")
projects_router.register("projects", project_views.ProjectViewSet, basename="organization-projects")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(projects_router.urls))
]
