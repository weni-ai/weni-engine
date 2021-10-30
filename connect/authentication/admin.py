from django.contrib import admin

from connect.authentication.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass
