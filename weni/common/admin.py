from django.contrib import admin

from weni.common.models import (
    Newsletter,
    Service,
    ServiceStatus,
    Organization,
    Project,
    OrganizationAuthorization,
    LogService,
)


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    pass


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(ServiceStatus)
class ServiceStatusAdmin(admin.ModelAdmin):
    pass


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    pass


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    pass


@admin.register(OrganizationAuthorization)
class OrganizationAuthorizationAdmin(admin.ModelAdmin):
    pass


@admin.register(LogService)
class LogServiceAdmin(admin.ModelAdmin):
    pass
