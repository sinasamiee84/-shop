from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Cart, CartItem, Discount, Order, OrderItem


class CartItemInline(TabularInline):
  model = CartItem
  extra = 0
  autocomplete_fields = ['product', 'variant']


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
  readonly_fields = ('created_at', 'updated_at')


class OrderItemInline(TabularInline):
  model = OrderItem
  extra = 0
  readonly_fields = (
      'product_title',
      'variant_title',
      'unit_price',
      'quantity',
      'total_price',
      'discount_amount',
  )
  can_delete = False


@admin.register(Order)
class OrderAdmin(ModelAdmin):
  list_display = (
      'id',
      'user',
      'full_name',
      'phone',
      'final_price',
      'status',
      'created_at',
  )
  list_filter = ('status', 'created_at')
  search_fields = ('user__phone', 'full_name', 'phone', 'id')
  inlines = [OrderItemInline]
  readonly_fields = (
      'total_price',
      'product_discount_amount',
      'cart_discount_amount',
      'final_price',
      'created_at',
  )
  list_editable = ('status',)


@admin.register(Discount)
class DiscountAdmin(ModelAdmin):
  list_display = (
      'code',
      'title',
      'discount_type',
      'apply_type',
      'value',
      'is_active',
      'active_from',
      'active_to',
      'used_count',
  )
  list_filter = ('discount_type', 'apply_type', 'is_active', 'created_at')
  search_fields = ('code', 'title')
  filter_horizontal = (
      'products',
  )  # انتخاب آسان محصولات مشمول تخفیف در پنل ادمین
  list_editable = ('is_active',)
  fieldsets = (
      (
          'اطلاعات اصلی',
          {
              'fields': (
                  'code',
                  'title',
                  'discount_type',
                  'apply_type',
                  'value',
                  'is_active',
              )
          },
      ),
      (
          'مشمولین (مخصوص تخفیف محصول)',
          {
              'fields': ('products',),
              'description': (
                  'اگر نوع اعمال تخفیف روی «محصولات خاص» است، محصولات موردنظر'
                  ' را اینجا انتخاب کنید.'
              ),
          },
      ),
      (
          'محدودیت‌ها و تاریخ اعتبار',
          {
              'fields': (
                  'min_purchase_amount',
                  'usage_limit',
                  'used_count',
                  'active_from',
                  'active_to',
              )
          },
      ),
  )

