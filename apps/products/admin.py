from django.contrib import admin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from .models import Color, Category, Brand, BrandModel, Product, ProductVariant, ProductImage


# نمایش تصاویر به‌صورت خطی (Stacked)
class ProductImageInline(StackedInline):
    model = ProductImage
    extra = 1
    verbose_name = "تصویر"
    verbose_name_plural = "تصاویر اسلایدی"


# نمایش واریانت‌ها به‌صورت جدول‌بندی شده (Tabular) برای ورود سریع‌تر قیمت و موجودی
class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    verbose_name = "واریانت"
    verbose_name_plural = "واریانت‌های محصول (رنگ و سایز)"


@admin.register(Color)
class ColorAdmin(ModelAdmin):
    list_display = ("name",)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ("name", "country")
    list_filter = ("country",)


@admin.register(BrandModel)
class BrandModelAdmin(ModelAdmin):
    list_display = ("name", "brand")
    list_filter = ("brand",)


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ("title", "brand", "price", "quantity", "is_active")
    list_filter = ("brand", "category", "gender", "is_active")
    search_fields = ("title", "brand__name")
    prepopulated_fields = {"slug": ("title",)}

    # اضافه کردن تصاویر و واریانت‌ها به صفحه ویرایش محصول
    inlines = [ProductVariantInline, ProductImageInline]

    fieldsets = (
        ("اطلاعات اصلی", {
            "fields": ("title", "slug", "category", "brand", "model", "price", "description")
        }),
        ("مشخصات پیش‌فرض (فعلی)", {
            "fields": ("color", "size", "gender", "quantity")
        }),
        ("وضعیت", {
            "fields": ("is_active",)
        }),
    )


# ثبت مستقل واریانت‌ها برای مدیریت کلی در پنل ادمین
@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = ("product", "color", "size", "price", "quantity", "sku")
    list_filter = ("color", "size", "product__brand")
    search_fields = ("product__title", "sku")


@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    list_display = ("product", "image_preview")

    def image_preview(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                               obj.image.url)
        return "-"

    image_preview.short_description = "پیش‌نمایش"
