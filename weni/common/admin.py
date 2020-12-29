from django.contrib import admin

from weni.common.models import Newsletter, Service, ServiceStatus


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    pass


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(ServiceStatus)
class ServiceStatusAdmin(admin.ModelAdmin):
    pass
