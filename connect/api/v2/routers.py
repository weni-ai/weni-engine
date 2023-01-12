from django.urls import path, include
from rest_framework_nested import routers

from connect.api.v2.organizations import views as organization_views


router = routers.SimpleRouter()
router.register('organizations', organization_views.OrganizationViewSet, basename="organizations")

urlpatterns = [
    path("", include(router.urls)),
]
