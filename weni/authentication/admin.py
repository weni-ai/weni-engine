from django.contrib import admin

from weni.authentication.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass
