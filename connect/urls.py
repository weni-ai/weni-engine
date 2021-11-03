"""weni URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from drf_yasg2 import openapi
from drf_yasg2.views import get_schema_view
from rest_framework import permissions

from connect.api.v1 import urls as rookly_api_v1_urls
from connect.api.grpc.project.handlers import grpc_handlers as grpc_project_handlers
from connect.billing.views import StripeHandler


schema_view = get_schema_view(
    openapi.Info(
        title="API Documentation",
        default_version="v1.0.12",
        license=openapi.License(name="GPL-3.0 License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("", schema_view.with_ui("redoc")),
    path("admin/", admin.site.urls),
    path("v1/", include(rookly_api_v1_urls)),
    url(r"^handlers/stripe/$", StripeHandler.as_view(), name="handlers.stripe_handler"),
]

urlpatterns += staticfiles_urlpatterns()


def grpc_handlers(server):
    grpc_project_handlers(server)


if settings.DEBUG:

    def render_template(template_name, **kwargs):
        def wrapper(request):
            from django.shortcuts import render

            return render(request, template_name, kwargs)

        return wrapper

    urlpatterns += [
        path(
            "emails/",
            include(
                [
                    path(
                        "change-password/",
                        render_template(
                            "authentication/emails/change_password.html",
                            name="User",
                            base_url=settings.BASE_URL,
                        ),
                    ),
                    path(
                        "invite-organization/",
                        render_template(
                            "authentication/emails/invite_organization.html",
                            base_url=settings.BASE_URL,
                            organization_name="Org Test",
                        ),
                    ),
                    path(
                        "project-create/",
                        render_template(
                            "authentication/emails/project_create.html",
                            base_url=settings.BASE_URL,
                            first_name="Daniel Yohan",
                            project_name="Project Test",
                            organization_name="Org Test",
                        ),
                    ),
                    path(
                        "remove-permission-organization/",
                        render_template(
                            "authentication/emails/remove_permission_organization.html",
                            base_url=settings.BASE_URL,
                            first_name="Daniel Yohan",
                            organization_name="Org Test",
                        ),
                    ),
                    path(
                        "delete-organization/",
                        render_template(
                            "authentication/emails/delete_organization.html",
                            base_url=settings.BASE_URL,
                            first_name="Daniel Yohan",
                            organization_name="Org Test",
                        ),
                    ),
                ]
            ),
        )
    ]
