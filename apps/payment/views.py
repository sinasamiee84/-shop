from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Order
from .models import Payment
from .services import get_zarinpal_config, zarinpal_request, zarinpal_verify


@login_required
def start_payment(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
    )

    if order.status != Order.OrderStatus.PENDING:
        messages.error(request, "این سفارش قبلاً پردازش شده یا قابل پرداخت نیست.")
        return redirect("cart:order_list")

    # قیمت‌های فروشگاه تومان هستند؛ مبلغ ارسالی به زرین‌پال باید ریال باشد.
    amount_in_rial = int(order.final_price) * 10

    payment = Payment.objects.create(
        order=order,
        user=request.user,
        amount=amount_in_rial,
        status=Payment.Status.PENDING,
    )

    callback_url = request.build_absolute_uri(
        reverse("payment:verify")
    )

    success, authority, error_msg = zarinpal_request(payment, callback_url)

    if success and authority:
        payment.authority = authority
        payment.save(update_fields=["authority"])

        _, _, _, start_pay_url = get_zarinpal_config()
        return redirect(f"{start_pay_url}{authority}")

    payment.status = Payment.Status.FAILED
    payment.gateway_message = error_msg or "زرین‌پال درخواست پرداخت را نپذیرفت."
    payment.save(update_fields=["status", "gateway_message"])

    messages.error(
        request,
        f"خطا در ایجاد تراکنش: {payment.gateway_message}",
    )
    return redirect("cart:order_detail", pk=order.pk)


def verify_payment(request):
    authority = request.GET.get("Authority")
    gateway_status = request.GET.get("Status")

    if not authority:
        messages.error(request, "شناسه پرداخت از طرف درگاه دریافت نشد.")
        return redirect("cart:order_list")

    payment = get_object_or_404(
        Payment.objects.select_related("order"),
        authority=authority,
    )

    # جلوگیری از پردازش دوباره callback برای پرداخت موفق
    if payment.status == Payment.Status.SUCCESS:
        return render(
            request,
            "payment/payment_success.html",
            {"payment": payment},
        )

    if gateway_status != "OK":
        payment.status = Payment.Status.CANCELED
        payment.gateway_message = "پرداخت توسط کاربر لغو شد."
        payment.save(update_fields=["status", "gateway_message"])

        messages.warning(request, "پرداخت توسط شما لغو شد.")
        return redirect("cart:order_detail", pk=payment.order_id)

    success, ref_id, error_msg = zarinpal_verify(
        payment.amount,
        authority,
    )

    if not success:
        payment.status = Payment.Status.FAILED
        payment.gateway_message = error_msg or "تأیید تراکنش ناموفق بود."
        payment.save(update_fields=["status", "gateway_message"])

        return render(
            request,
            "payment/payment_failed.html",
            {
                "payment": payment,
                "error_msg": payment.gateway_message,
            },
        )

    payment.status = Payment.Status.SUCCESS
    payment.ref_id = str(ref_id) if ref_id else ""
    payment.paid_at = timezone.now()
    payment.gateway_message = ""
    payment.save(
        update_fields=[
            "status",
            "ref_id",
            "paid_at",
            "gateway_message",
        ]
    )

    order = payment.order
    order.status = Order.OrderStatus.PAID
    order.save(update_fields=["status"])

    return render(
        request,
        "payment/payment_success.html",
        {"payment": payment},
    )
