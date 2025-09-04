from django.contrib import admin
from django import forms

from connect.common.models import (
    Newsletter,
    Service,
    ServiceStatus,
    Organization,
    Project,
    OrganizationAuthorization,
    NewsletterLanguage,
    BillingPlan,
    NewsletterOrganization,
)


class BillingPlanAdminForm(forms.ModelForm):
    class Meta:
        model = BillingPlan
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        new_flag = cleaned_data.get("trial_extension_enabled")
        original_flag = self.initial.get(
            "trial_extension_enabled", self.instance.trial_extension_enabled
        )

        if self.instance.pk and original_flag and not new_flag:
            raise forms.ValidationError(
                "Trial extension cannot be disabled once enabled."
            )

        if (not original_flag) and new_flag:
            if self.instance.plan != BillingPlan.PLAN_TRIAL:
                raise forms.ValidationError(
                    "Trial extension is only available for organizations on the trial plan."
                )
            if not self.instance.trial_end_date:
                raise forms.ValidationError(
                    "Trial end date is not set for this organization."
                )
            import pendulum

            if pendulum.now() <= pendulum.instance(self.instance.trial_end_date):
                raise forms.ValidationError(
                    "Trial extension can only be enabled after the first trial ends."
                )

        return cleaned_data

    def save(self, commit=True):
        original_flag = self.initial.get(
            "trial_extension_enabled", self.instance.trial_extension_enabled
        )
        instance = super().save(commit=False)
        new_flag = self.cleaned_data.get("trial_extension_enabled")
        if (not original_flag) and new_flag:
            if instance.pk is None and commit:
                instance.trial_extension_enabled = False
                instance.save()
            elif instance.pk is not None:
                BillingPlan.objects.filter(pk=instance.pk).update(
                    trial_extension_enabled=False
                )
            instance.enable_trial_extension()
        else:
            if commit:
                instance.save()
        return instance


class ProxyOrg(Organization):
    class Meta:
        proxy = True
        verbose_name = "Organization Authorization"
        verbose_name_plural = "Organization Authorization"


class BillingPlanInline(admin.TabularInline):
    model = BillingPlan
    form = BillingPlanAdminForm
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
        "trial_end_date",
        "trial_extension_end_date",
    ]
    can_delete = False


class OrganizationAuthorizationInline(admin.TabularInline):
    model = OrganizationAuthorization
    extra = 1
    min_num = 1
    can_delete = False
    raw_id_fields = ("user",)


class OrganizationAdmin(admin.ModelAdmin):
    inlines = [BillingPlanInline]
    search_fields = ["name", "inteligence_organization"]

    def save_model(self, request, obj, form, change):
        if obj.is_suspended != form.initial.get("is_suspended", False):
            if not obj.is_suspended:
                NewsletterOrganization.destroy_newsletter(obj)
        super().save_model(request, obj, form, change)


class ServiceStatusInline(admin.TabularInline):
    model = ServiceStatus


class ProjectAdmin(admin.ModelAdmin):
    inlines = [ServiceStatusInline]
    search_fields = ["name", "organization__name", "organization__uuid"]


class NewsletterLanguageInline(admin.TabularInline):
    model = NewsletterLanguage
    min_num = 2
    can_delete = False


class NewsletterAdmin(admin.ModelAdmin):
    inlines = [NewsletterLanguageInline]


class OrgAuthInline(admin.TabularInline):
    model = OrganizationAuthorization
    extra = 0
    min_num = 1
    can_delete = False
    autocomplete_fields = ["user"]


class ProxyOrgAdmin(admin.ModelAdmin):
    inlines = [OrgAuthInline]
    fields = ("name",)
    readonly_fields = ("name",)
    search_fields = ["name", "inteligence_organization", "uuid"]


admin.site.register(Newsletter, NewsletterAdmin)
admin.site.register(Service)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(ProxyOrg, ProxyOrgAdmin)
