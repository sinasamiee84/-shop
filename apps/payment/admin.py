from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = (
        "id",
        "order",
        "user",
        "amount",
        "gateway",
        "status",
        "ref_id",
        "paid_at",
        "created_at",
    )
    list_filter = ("status", "gateway", "created_at")
    search_fields = ("order__id", "user__phone", "authority", "ref_id")
    readonly_fields = (
        "order",
        "user",
        "gateway",
        "amount",
        "authority",
        "ref_id",
        "gateway_message",
        "paid_at",
        "created_at",
        "updated_at",
    )
