from django.conf import settings
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار پرداخت"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"
        CANCELED = "canceled", "لغو شده"
        EXPIRED = "expired", "منقضی شده"

    class Gateway(models.TextChoices):
        ZARINPAL = "zarinpal", "زرین‌پال"

    order = models.ForeignKey(
        "cart.Order",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="سفارش",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="کاربر",
    )
    gateway = models.CharField(
        max_length=30,
        choices=Gateway.choices,
        default=Gateway.ZARINPAL,
        verbose_name="درگاه",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت",
    )
    # مبلغ ذخیره شده به ریال (مبلغ سفارش ضربدر 10)
    amount = models.PositiveBigIntegerField(
        verbose_name="مبلغ به ریال",
    )
    authority = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Authority",
    )
    ref_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="شماره پیگیری",
    )
    gateway_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="پیام درگاه",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان پرداخت",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"

    def __str__(self):
        return f"پرداخت سفارش #{self.order_id} - {self.get_status_display()}"

