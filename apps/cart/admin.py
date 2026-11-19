from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Cart, CartItem, Discount, Order, OrderItem


class CartItemInline(TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ['product', 'variant']


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'variant', 'quantity', 'total_price')


@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = (
        'id',
        'user',
        'session_key',
        'cart_discount',
        'created_at',
        'updated_at',
    )
    list_filter = ('created_at',)
    search_fields = ('user__phone', 'user__email', 'session_key')
    inlines = [CartItemInline]


@admin.action(description="علامت‌گذاری به‌عنوان ارسال‌شده")
def mark_orders_posted(modeladmin, request, queryset):
    updated = queryset.filter(
        status="paid"
    ).update(
        status="posted"
    )

    modeladmin.message_user(
        request,
        f"{updated} سفارش به‌عنوان ارسال‌شده ثبت شد.",
    )


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    actions = [mark_orders_posted]

    list_display = (
        "id",
        "user",
        "full_name",
        "phone",
        "final_price",
        "status",
        "created_at",
    )
    list_filter = ('status', 'created_at')
    search_fields = ('full_name', 'phone', 'address')
    inlines = [OrderItemInline]

    fieldsets = (
        ('اطلاعات کاربر و سفارش', {
            'fields': ('user', 'status', 'created_at')
        }),
        ('اطلاعات گیرنده', {
            'fields': ('full_name', 'phone', 'address', 'postal_code')
        }),
        ('اطلاعات مالی', {
            'fields': ('total_price', 'product_discount_amount', 'cart_discount_amount', 'final_price')
        }),
    )

    readonly_fields = (
        'user', 'status', 'created_at', 'full_name', 'phone',
        'address', 'postal_code', 'total_price', 'product_discount_amount',
        'cart_discount_amount', 'final_price'
    )


@admin.register(Discount)
class DiscountAdmin(ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'apply_type', 'is_active')
