import requests
from django.conf import settings


def get_zarinpal_config():
    is_sandbox = getattr(settings, "ZARINPAL_SANDBOX", True)
    merchant_id = getattr(settings, "ZARINPAL_MERCHANT_ID", "")

    if is_sandbox:
        request_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        start_pay_url = "https://sandbox.zarinpal.com/pg/StartPay/"
    else:
        request_url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
        verify_url = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
        start_pay_url = "https://payment.zarinpal.com/pg/StartPay/"

    return merchant_id, request_url, verify_url, start_pay_url


def _error_message(response_data, default_message):
    errors = response_data.get("errors") or {}
    if isinstance(errors, dict):
        # بررسی خطاهای ولیدیشن لاراول/زرین‌پال
        messages_list = errors.get("message")
        if isinstance(messages_list, list):
            return " | ".join(str(m) for m in messages_list)
        if isinstance(messages_list, str):
            return messages_list
    return default_message


def zarinpal_request(payment, callback_url):
    merchant_id, request_url, _, _ = get_zarinpal_config()

    if not merchant_id:
        return False, None, "شناسه پذیرنده زرین‌پال در تنظیمات تعریف نشده است."

    user = payment.user

    # ساخت متادیتای امن و مطمئن برای زرین‌پال (فقط مقادیر غیرخالی به صورت رشته)
    metadata = {}
    if user and hasattr(user, "phone") and user.phone:
        metadata["mobile"] = str(user.phone)
    if user and hasattr(user, "email") and user.email:
        metadata["email"] = str(user.email)

    metadata["order_id"] = str(payment.order_id)

    payload = {
        "merchant_id": merchant_id,
        "amount": int(payment.amount),
        "description": f"پرداخت سفارش شماره {payment.order_id} در فروشگاه",
        "callback_url": callback_url,
        "metadata": metadata,
    }

    try:
        response = requests.post(request_url, json=payload, timeout=15)
        response_data = response.json()
    except requests.exceptions.RequestException as exc:
        return False, None, f"خطای ارتباط با زرین‌پال: {exc}"
    except ValueError:
        return False, None, "پاسخ دریافتی از زرین‌پال قابل خواندن نیست."

    data = response_data.get("data") or {}

    if response.ok and data.get("code") == 100 and data.get("authority"):
        return True, data["authority"], None

    err_msg = _error_message(response_data, "زرین‌پال درخواست پرداخت را نپذیرفت.")
    return False, None, err_msg


def zarinpal_verify(amount, authority):
    merchant_id, _, verify_url, _ = get_zarinpal_config()

    if not merchant_id:
        return False, None, "شناسه پذیرنده زرین‌پال در تنظیمات تعریف نشده است."

    payload = {
        "merchant_id": merchant_id,
        "amount": int(amount),
        "authority": authority,
    }

    try:
        response = requests.post(verify_url, json=payload, timeout=15)
        response_data = response.json()
    except requests.exceptions.RequestException as exc:
        return False, None, f"خطای ارتباط با زرین‌پال: {exc}"
    except ValueError:
        return False, None, "پاسخ دریافتی از زرین‌پال قابل خواندن نیست."

    data = response_data.get("data") or {}

    # کد 100 پرداخت موفق و 101 پرداختی است که قبلاً تأیید شده است.
    if response.ok and data.get("code") in (100, 101):
        return True, data.get("ref_id"), None

    return (
        False,
        None,
        _error_message(response_data, "تراکنش ناموفق بود یا تأیید نشد."),
    )
