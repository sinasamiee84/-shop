from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin

from .models import CustomUser, OtpCode


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ("phone_number", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("phone_number", "first_name", "last_name")
    ordering = ("phone_number",)
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("اطلاعات شخصی", {"fields": ("first_name", "last_name", "email")}),
        ("دسترسی‌ها", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone_number", "password1", "password2")}),
    )


@admin.register(OtpCode)
class OtpCodeAdmin(ModelAdmin):
    list_display = ("phone_number", "purpose", "created_at", "attempts", "is_used")
    list_filter = ("purpose", "is_used")
    search_fields = ("phone_number",)
    readonly_fields = ("code_hash",)
