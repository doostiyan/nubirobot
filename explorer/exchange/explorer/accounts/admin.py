from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
import typing


class CustomUserAdmin(UserAdmin):
    model: typing.Type[User]
    list_display = ("id", "username", "email", "last_login", "is_superuser", "is_active", "is_staff", "date_joined")
    list_filter = ("date_joined", "is_active", "is_staff", "is_superuser")
    search_fields = ("id", "email", "username")
    readonly_fields = ("id", "date_joined")


admin.site.register(User, CustomUserAdmin)
