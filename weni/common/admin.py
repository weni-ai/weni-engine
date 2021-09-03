from django.contrib import admin

from weni.common.models import (
    Newsletter,
    Service,
    ServiceStatus,
    Organization,
    Project,
    OrganizationAuthorization,
    NewsletterLanguage,
)


class OrganizationAuthorizationInline(admin.TabularInline):
    model = OrganizationAuthorization
    extra = 1
    min_num = 1
    can_delete = False


class OrganizationAdmin(admin.ModelAdmin):
    inlines = [OrganizationAuthorizationInline]
    search_fields = ["name", "inteligence_organization"]


class ServiceStatusInline(admin.TabularInline):
    model = ServiceStatus


class ProjectAdmin(admin.ModelAdmin):
    inlines = [ServiceStatusInline]


class NewsletterLanguageInline(admin.TabularInline):
    model = NewsletterLanguage
    min_num = 2
    can_delete = False


class NewsletterAdmin(admin.ModelAdmin):
    inlines = [NewsletterLanguageInline]


admin.site.register(Newsletter, NewsletterAdmin)
admin.site.register(Service)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Organization, OrganizationAdmin)
