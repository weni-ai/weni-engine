from django.contrib import admin

from connect.common.models import (
    Newsletter,
    Service,
    ServiceStatus,
    Organization,
    Project,
    OrganizationAuthorization,
    NewsletterLanguage,
    BillingPlan,
)


class BillingPlanInline(admin.TabularInline):
    model = BillingPlan
    extra = 1
    min_num = 1
    readonly_fields = [
        "payment_method",
        "last_invoice_date",
        "next_due_date",
        "termination_date",
        "stripe_configured_card",
        "final_card_number",
        "card_expiration_date",
        "cardholder_name",
        "card_brand",
    ]
    can_delete = False


class OrganizationAuthorizationInline(admin.TabularInline):
    model = OrganizationAuthorization
    extra = 1
    min_num = 1
    can_delete = False


class OrganizationAdmin(admin.ModelAdmin):
    inlines = [BillingPlanInline, OrganizationAuthorizationInline]
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
