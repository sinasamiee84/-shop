from django.db import models
from django.utils.text import slugify
import uuid
from django.urls import reverse

class Color(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="رنگ")

    class Meta:
        verbose_name = "رنگ"
        verbose_name_plural = "رنگ‌ها"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name="نامک (Slug)",
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="نام برند")
    country = models.CharField(max_length=50, verbose_name="کشور سازنده")

    class Meta:
        verbose_name = "برند"
        verbose_name_plural = "برندها"

    def __str__(self):
        return self.name


class BrandModel(models.Model):
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name="models",
        verbose_name="برند",
    )
    name = models.CharField(max_length=50, verbose_name="نام مدل")

    class Meta:
        verbose_name = "مدل برند"
        verbose_name_plural = "مدل‌های برند"
        unique_together = ("brand", "name")

    def __str__(self):
        return f"{self.brand.name} - {self.name}"


class Product(models.Model):
    class Size(models.TextChoices):
        SMALL = ("S", "اسمال")
        MEDIUM = ("M", "مدیوم")
        LARGE = ("L", "لارج")
        XLARGE = ("XL", "ایکس لارج")

    class Gender(models.TextChoices):
        MALE = ("M", "مردانه")
        FEMALE = ("F", "زنانه")
        UNISEX = ("U", "یونیسکس")

    title = models.CharField(max_length=50, unique=True, verbose_name="عنوان محصول")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name="نامک (Slug)",
    )
    description = models.TextField(
        verbose_name="توضیحات محصول",
        blank=True,
        null=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="دسته‌بندی",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        verbose_name="برند",
    )
    model = models.ForeignKey(
        BrandModel,
        on_delete=models.CASCADE,
        verbose_name="مدل",
        null=True,
        blank=True,
    )

    # این فیلدها فعلاً باقی مانده‌اند تا ویوها و قالب‌های فعلی نشکنند.
    # پس از انتقال داده‌ها به ProductVariant می‌توان آن‌ها را حذف کرد.
    color = models.ForeignKey(
        Color,
        on_delete=models.CASCADE,
        verbose_name="رنگ",
        null=True,
        blank=True,
    )
    size = models.CharField(
        max_length=5,
        choices=Size.choices,
        default=Size.SMALL,
        null=True,
        blank=True,
        verbose_name="سایز",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="موجودی")
    price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name="قیمت (تومان)",
    )

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        default=Gender.FEMALE,
        verbose_name="جنسیت",
    )
    blog_posts = models.ManyToManyField(
        "blogs.BlogPost",
        blank=True,
        related_name="products",
        verbose_name="مقالات آموزشی",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")
    def get_absolute_url(self):

        return reverse('products:detail', kwargs={'slug': self.slug})
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)
            self.slug = base_slug

            if Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"

    def __str__(self):
        return f"{self.brand.name} | {self.title}"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="محصول",
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="رنگ",
    )
    size = models.CharField(
        max_length=5,
        choices=Product.Size.choices,
        null=True,
        blank=True,
        verbose_name="سایز",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name="قیمت (تومان)",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="موجودی")
    sku = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="کد کالا",
    )

    class Meta:
        verbose_name = "واریانت محصول"
        verbose_name_plural = "واریانت‌های محصول"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "color", "size"],
                name="unique_product_variant_color_size",
            )
        ]

    def __str__(self):
        color_name = self.color.name if self.color else "بدون رنگ"
        size_name = self.get_size_display() if self.size else "بدون سایز"
        return f"{self.product.title} - {color_name} - {size_name}"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="تصویر محصول",
    )
    image = models.ImageField(
        upload_to="products/images/",
        verbose_name="تصویر",
    )
    alt_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="متن جایگزین (Alt)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ بارگذاری",
    )

    class Meta:
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"

    def __str__(self):
        return f"تصویر {self.id} برای {self.product.title}"
