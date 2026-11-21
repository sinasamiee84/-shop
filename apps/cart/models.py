from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.products.models import Product, ProductVariant  # فرض بر این است که مدل‌های محصول اینجاست


class Discount(models.Model):
  class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'درصدی'
    FIXED = 'fixed', 'مبلغ ثابت'

  class ApplyType(models.TextChoices):
    PRODUCT = 'product', 'محصولات خاص'
    CART = 'cart', 'کل فاکتور (سبد خرید)'

  code = models.CharField(
      max_length=50, unique=True, verbose_name='کد تخفیف'
  )
  title = models.CharField(
      max_length=255, blank=True, verbose_name='عنوان تخفیف'
  )
  discount_type = models.CharField(
      max_length=20,
      choices=DiscountType.choices,
      default=DiscountType.PERCENTAGE,
      verbose_name='نوع تخفیف',
  )
  apply_type = models.CharField(
      max_length=20,
      choices=ApplyType.choices,
      default=ApplyType.PRODUCT,
      verbose_name='محل اعمال تخفیف',
  )

  # مقدار تخفیف (اگر درصدی باشد بین 1 تا 100، اگر مبلغ ثابت باشد به تومان/ریال)
  value = models.DecimalField(
      max_digits=12, decimal_places=0, verbose_name='مقدار تخفیف'
  )
  max_discount_amount = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      null=True,
      blank=True,
      verbose_name='سقف مبلغ تخفیف',
      help_text='اختیاری؛ فقط برای تخفیف درصدی استفاده می‌شود.',
  )

  # اگر تخفیف برای محصولات خاصی باشد (می‌تواند خالی باشد یعنی روی همه محصولات آن دسته اعمال شود یا فقط محصولات انتخابی)
  products = models.ManyToManyField(
      Product,
      blank=True,
      related_name='discounts',
      verbose_name='محصولات مشمول تخفیف',
  )

  # محدودیت‌ها
  min_purchase_amount = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name='حداقل مبلغ خرید',
  )
  usage_limit = models.PositiveIntegerField(
      null=True, blank=True, verbose_name='حداکثر دفعات استفاده کل'
  )
  used_count = models.PositiveIntegerField(
      default=0, verbose_name='تعداد دفعات استفاده‌شده'
  )

  active_from = models.DateTimeField(
      null=True, blank=True, verbose_name='معتبر از تاریخ'
  )
  active_to = models.DateTimeField(
      null=True, blank=True, verbose_name='معتبر تا تاریخ'
  )
  is_active = models.BooleanField(default=True, verbose_name='فعال')

  created_at = models.DateTimeField(
      auto_now_add=True, verbose_name='تاریخ ایجاد'
  )

  class Meta:
    verbose_name = 'کد تخفیف'
    verbose_name_plural = 'کدهای تخفیف'

  def __str__(self):
    return f'{self.title} ({self.code})'

class UserDiscountUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discount_usages",
        verbose_name="کاربر",
    )
    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        related_name="usages",
        verbose_name="کد تخفیف",
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discount_usages",
        verbose_name="سفارش",
    )
    used_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ استفاده")

    class Meta:
        verbose_name = "استفاده از کد تخفیف"
        verbose_name_plural = "تاریخچه استفاده از کدهای تخفیف"
        # مهم: هر کاربر فقط یک‌بار می‌تواند برای هر کد این رکورد را داشته باشد
        constraints = [
            models.UniqueConstraint(
                fields=["user", "discount"],
                name="unique_user_discount_usage"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.discount.code}"

class Cart(models.Model):
  user = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.CASCADE,
      null=True,
      blank=True,
      verbose_name='کاربر',
  )
  session_key = models.CharField(
      max_length=255, null=True, blank=True, verbose_name='شناسه جلسه مهمان'
  )
  cart_discount = models.ForeignKey(
      Discount,
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      limit_choices_to={'apply_type': Discount.ApplyType.CART},
      verbose_name='تخفیف روی فاکتور',
  )
  created_at = models.DateTimeField(
      auto_now_add=True, verbose_name='تاریخ ایجاد'
  )
  updated_at = models.DateTimeField(
      auto_now=True, verbose_name='تاریخ بروزرسانی'
  )

  class Meta:
    verbose_name = 'سبد خرید'
    verbose_name_plural = 'سبدهای خرید'

  def __str__(self):
    return f'سبد خرید #{self.id} - {self.user or self.session_key}'


class CartItem(models.Model):
  cart = models.ForeignKey(
      Cart,
      on_delete=models.CASCADE,
      related_name='items',
      verbose_name='سبد خرید',
  )
  product = models.ForeignKey(
      Product, on_delete=models.CASCADE, verbose_name='محصول'
  )
  variant = models.ForeignKey(
      ProductVariant,
      on_delete=models.CASCADE,
      null=True,
      blank=True,
      verbose_name='نوع/متغیر محصول',
  )
  quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد')

  class Meta:
    verbose_name = 'آیتم سبد خرید'
    verbose_name_plural = 'آیتم‌های سبد خرید'

  def __str__(self):
    return f'{self.quantity} عدد از {self.product.title}'


class Order(models.Model):
  class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'در انتظار پرداخت'
    PAID = 'paid', 'پرداخت‌شده'
    CANCELLED = 'cancelled', 'لغوشده'
    POSTED = 'posted', 'ارسال‌شده'

  user = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.PROTECT,
      related_name='orders',
      verbose_name='کاربر',
  )
  status = models.CharField(
      max_length=20,
      choices=OrderStatus.choices,
      default=OrderStatus.PENDING,
      verbose_name='وضعیت سفارش',
  )

  # مبالغ مالی
  total_price = models.DecimalField(
      max_digits=12, decimal_places=0, verbose_name='مجمع کل (بدون تخفیف)'
  )
  product_discount_amount = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name='مجموع تخفیف محصولات',
  )
  shipping_cost = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="هزینه ارسال")
  cart_discount_amount = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name='تخفیف روی کل فاکتور',
  )
  final_price = models.DecimalField(
      max_digits=12, decimal_places=0, verbose_name='مبلغ قابل پرداخت نهایی'
  )

  # اطلاعات ارسال و آدرس
  full_name = models.CharField(max_length=255, verbose_name='نام گیرنده')
  phone = models.CharField(max_length=15, verbose_name='شماره تماس')
  address = models.TextField(verbose_name='آدرس پستی')
  postal_code = models.CharField(max_length=20, verbose_name='کد پستی')
  cart_discount = models.ForeignKey(
      Discount,
      on_delete=models.SET_NULL,
      null=True,
      blank=True,
      verbose_name="تخفیف اعمال‌شده روی سفارش",
  )
  created_at = models.DateTimeField(
      auto_now_add=True, verbose_name='تاریخ ثبت سفارش'
  )

  class Meta:
    verbose_name = 'سفارش'
    verbose_name_plural = 'سفارش‌ها'

  def __str__(self):
    return f'سفارش #{self.id} - {self.user}'


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سفارش",
    )
    # اضافه کردن ارتباط با واریانت (null=True برای جلوگیری از خطای داده‌های قبلی)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name="واریانت محصول",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name="محصول",
    )
    product_title = models.CharField(
        max_length=255, verbose_name="عنوان محصول در زمان خرید"
    )
    variant_title = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="مشخصه متغیر"
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name="قیمت واحد"
    )
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    total_price = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name="قیمت کل"
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name="تخفیف اعمال شده روی این آیتم",
    )

    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self):
        return f"{self.quantity}x {self.product_title} در سفارش #{self.order.id}"
