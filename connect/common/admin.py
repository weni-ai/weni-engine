from django.contrib import admin

from connect.common.models import DashboardNewsletter


@admin.register(DashboardNewsletter)
class DashboardNewsletterAdmin(admin.ModelAdmin):
    pass
