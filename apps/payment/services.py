import requests
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from apps.cart.models import Order , UserDiscountUsage , Discount , Cart
from django.db.models import  F
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




@transaction.atomic
def verify_payment_and_complete_order(order_id):
    """
    کسر موجودی و تغییر وضعیت سفارش به paid را اتمیک انجام می‌دهد.
    این تابع فقط پس از تأیید موفق پرداخت نزد درگاه فراخوانی شود.
    """
    order = (
        Order.objects
        .select_for_update()
        .filter(pk=order_id)
        .first()
    )

    if order is None:
        return False, "سفارش پیدا نشد."

    # callback ممکن است تکراری باشد؛ سفارش پرداخت‌شده را دوباره پردازش نکن.
    if order.status == Order.OrderStatus.PAID:
        return True, "این سفارش قبلاً پرداخت شده است."

    if order.status != Order.OrderStatus.PENDING:
        return False, "این سفارش در وضعیت قابل پرداخت نیست."

    items = list(
        order.items
        .select_related("product", "variant")
        .all()
    )

    if not items:
        return False, "سفارش آیتمی ندارد."

    # ابتدا همهٔ موجودی‌ها را قفل و بررسی می‌کنیم؛
    # تا پیش از اطمینان از موجودی همهٔ آیتم‌ها، چیزی کم نمی‌شود.
    for item in items:
        if item.variant_id:
            variant = (
                type(item.variant).objects
                .select_for_update()
                .filter(pk=item.variant_id)
                .first()
            )

            if variant is None:
                return False, f"واریانت محصول «{item.product_title}» پیدا نشد."

            item.variant = variant

            if variant.quantity < item.quantity:
                return False, f"موجودی «{item.product_title}» برای این سفارش کافی نیست."

        elif item.product_id:
            product = (
                type(item.product).objects
                .select_for_update()
                .filter(pk=item.product_id)
                .first()
            )

            if product is None:
                return False, f"محصول «{item.product_title}» پیدا نشد."

            item.product = product

            if product.quantity < item.quantity:
                return False, f"موجودی «{item.product_title}» برای این سفارش کافی نیست."

        else:
            return False, f"محصول سفارش «{item.product_title}» دیگر در دسترس نیست."
    if order.cart_discount:
        # ۱. ثبت در جدول تاریخچه استفاده کاربر (جلوگیری از استفاده مجدد)
        UserDiscountUsage.objects.get_or_create(
            user=order.user,
            discount=order.cart_discount,
            defaults={"order": order}
        )

        # ۲. افزایش تعداد کل دفعات استفاده از کد تخفیف
        Discount.objects.filter(pk=order.cart_discount.pk).update(
            used_count=F("used_count") + 1
        )

        # ۳. پاک کردن تخفیف از روی سبد خرید فعال کاربر
        # (برای اینکه تخفیف روی سبد جدیدش باقی نماند)
        Cart.objects.filter(user=order.user).update(cart_discount=None)
    # پس از بررسی کامل، موجودی را کم می‌کنیم.
    for item in items:
        if item.variant_id:
            item.variant.quantity -= item.quantity
            item.variant.save(update_fields=["quantity"])
        else:
            item.product.quantity -= item.quantity
            item.product.save(update_fields=["quantity"])

    order.status = Order.OrderStatus.PAID
    order.save(update_fields=["status"])

    return True, "پرداخت تأیید شد و موجودی کسر گردید."
