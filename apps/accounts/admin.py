from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
 
from apps.accounts.models import User

# Register your models here.
 
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = ["role", "is_active"]
    readonly_fields = ["date_joined", "last_login"]
 
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informacion personal", {"fields": ("first_name", "last_name", "role")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
 
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )