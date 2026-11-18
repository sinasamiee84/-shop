from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    """مدیریت کاربر با شماره موبایل به جای نام کاربری."""

    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        if not phone_number:
            raise ValueError("شماره موبایل الزامی است.")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("سوپریوزر باید is_staff و is_superuser داشته باشد.")
        return self._create_user(phone_number, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None
    phone_number = models.CharField(max_length=11, unique=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone_number


class OtpCode(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register", "ثبت‌نام"
        RESET_PASSWORD = "reset_password", "فراموشی رمز عبور"
        CHANGE_PASSWORD = "change_password", "تغییر رمز عبور"

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="otp_codes",
        null=True,
        blank=True,
    )
    phone_number = models.CharField(max_length=11, null=True, blank=True, db_index=True)
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        blank=True,
        default="",
    )
    # هش کد (make_password) طول بیشتری از 100 کاراکتر دارد
    code_hash = models.CharField(max_length=255)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone_number} - {self.get_purpose_display()} - {self.created_at}"
