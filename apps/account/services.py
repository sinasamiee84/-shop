import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F
from django.utils import timezone

from .models import OtpCode

logger = logging.getLogger(__name__)

OTP_VALIDITY = timedelta(minutes=2)  # اعتبار کد و همان مدت انتظار برای ارسال مجدد
MAX_OTP_ATTEMPTS = 5                 # تعداد تلاش نادرست مجاز برای هر کد


class ActiveOtpExists(Exception):
    """برای این شماره و هدف، هنوز OTP معتبر وجود دارد."""


class OtpSendError(Exception):
    """ارسال پیامک کد تأیید ناموفق بود."""


def generate_otp_code():
    """تولید کد تصادفی شش‌رقمی."""
    return str(secrets.randbelow(900000) + 100000)


def send_otp_sms(phone_number, code):
    """ارسال کد از طریق کاوه‌نگار (الگوی verify lookup)."""
    if not settings.KAVENEGAR_API_KEY:
        if settings.DEBUG:
            print(f"OTP for {phone_number}: {code}")  # فقط در توسعه
            return
        raise OtpSendError("سرویس پیامک پیکربندی نشده است.")

    import kavenegar  # وابستگی اختیاری در زمان تست

    try:
        api = kavenegar.KavenegarAPI(settings.KAVENEGAR_API_KEY)
        api.verify_lookup({
            "receptor": phone_number,
            "token": code,
            "template": settings.KAVENEGAR_OTP_TEMPLATE,
        })
    except kavenegar.APIException as exc:
        logger.exception("Kavenegar API error for %s", phone_number)
        raise OtpSendError("ارسال پیامک با خطا مواجه شد.") from exc
    except kavenegar.HTTPException as exc:
        logger.exception("Kavenegar HTTP error for %s", phone_number)
        raise OtpSendError("ارتباط با سرویس پیامک برقرار نشد.") from exc


def create_otp(phone_number, purpose, user=None):
    """
    کد جدید می‌سازد و پیامک می‌کند.
    تا وقتی کد فعلی معتبر است، ActiveOtpExists برمی‌گرداند؛ این همان مکانیزم
    «زمان انتظار ارسال مجدد» در سمت سرور است.
    """
    now = timezone.now()

    if OtpCode.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        is_used=False,
        expires_at__gt=now,
    ).exists():
        raise ActiveOtpExists("برای این شماره هنوز کد معتبری وجود دارد.")

    # باطل کردن کدهای قبلی که هنوز علامت‌گذاری نشده‌اند
    OtpCode.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)

    raw_code = generate_otp_code()
    otp = OtpCode.objects.create(
        user=user,
        phone_number=phone_number,
        purpose=purpose,
        code_hash=make_password(raw_code),
        expires_at=now + OTP_VALIDITY,
    )

    try:
        send_otp_sms(phone_number, raw_code)
    except OtpSendError:
        # اگر پیامک نرفت، کد را بی‌اثر کن تا کاربر کد بی‌استفاده نداشته باشد
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise

    return raw_code


def verify_otp_code(phone_number, purpose, raw_code):
    """
    کد را بررسی می‌کند. با هر تلاش نادرست شمارنده افزایش می‌یابد و
    پس از MAX_OTP_ATTEMPTS تلاش، کد قفل (بی‌اثر) می‌شود.
    """
    now = timezone.now()

    otp_obj = (
        OtpCode.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_used=False,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )

    if otp_obj is None or otp_obj.attempts >= MAX_OTP_ATTEMPTS:
        return False

    if not check_password(raw_code, otp_obj.code_hash):
        OtpCode.objects.filter(pk=otp_obj.pk).update(attempts=F("attempts") + 1)
        return False

    otp_obj.is_used = True
    otp_obj.save(update_fields=["is_used"])
    return True
