from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView
from django.db.models import F
from .forms import CheckoutForm
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET

from .models import CartItem, Order, OrderItem, Product, ProductVariant, Discount,Cart,ProductVariant
from .services import (
    build_cart_summary,
    get_cart_for_request,
    check_and_expire_abandoned_carts,validate_discount_for_user,calculate_shipping_cost
)
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.http import JsonResponse  # حتماً این را در بالا ایمپورت کنید
from .services import is_discount_available

def product_url_with_variant(product, variant_id=None):
    """
    آدرس صفحه محصول را همراه با variant_id می‌سازد.
    اگر قبلاً variant_id در URL وجود داشته باشد، مقدار آن را جایگزین می‌کند.
    """

    product_url = product.get_absolute_url()

    if not variant_id:
        return product_url

    parts = urlsplit(product_url)

    # حذف variant_id قبلی، در صورت وجود
    query_params = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True
        )
        if key != "variant_id"
    ]

    # اضافه کردن واریانت انتخاب‌شده
    query_params.append(("variant_id", str(variant_id)))

    new_query = urlencode(query_params)

    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        new_query,
        parts.fragment,
    ))


class AddToCartView(View):
    def post(self, request, product_id):
        check_and_expire_abandoned_carts()

        product = get_object_or_404(
            Product,
            pk=product_id,
            is_active=True,
        )

        variant_id = request.POST.get("variant_id")

        try:
            requested_quantity = int(
                request.POST.get("quantity", "1")
            )
        except (TypeError, ValueError):
            requested_quantity = 1

        requested_quantity = max(requested_quantity, 1)

        cart = get_cart_for_request(request)

        try:
            with transaction.atomic():
                cart = Cart.objects.select_for_update().get(
                    pk=cart.pk
                )

                product = Product.objects.select_for_update().get(
                    pk=product_id,
                    is_active=True,
                )

                variant = None
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant.objects.select_for_update(),
                        pk=variant_id,
                        product_id=product.id,
                    )
                    available_quantity = variant.quantity
                else:
                    available_quantity = product.quantity

                # فقط هشدار می‌دهیم که موجودی انبار کافی نیست (اختیاری: اجازه می‌دهیم به سبد اضافه شود یا جلویش را بگیریم)
                if available_quantity < requested_quantity:
                    messages.error(
                        request,
                        f"موجودی انبار محدود است. موجودی فعلی: {available_quantity} عدد",
                    )
                    # اگر می‌خواهی اجازه ندهی اضافه شود، اینجا return کن
                    # اما برای اینکه کاربر بتواند کالا را در سبد داشته باشد، معمولاً سخت‌گیری را می‌گذاریم برای پرداخت

                cart_item, created = (
                    CartItem.objects
                    .select_for_update()
                    .get_or_create(
                        cart=cart,
                        product=product,
                        variant=variant,
                        defaults={
                            "quantity": 0,
                        },
                    )
                )

                # **دیگر از انبار کم نمی‌کنیم!**
                cart_item.quantity += requested_quantity
                cart_item.save(update_fields=["quantity"])

                cart.save(update_fields=["updated_at"])

        except ProductVariant.DoesNotExist:
            messages.error(
                request,
                "واریانت انتخاب‌شده معتبر نیست.",
            )
            return redirect(product.get_absolute_url())

        messages.success(
            request,
            "محصول با موفقیت به سبد خرید اضافه شد.",
        )

        return redirect(
            product_url_with_variant(
                product,
                variant_id,
            )
        )


class CartView(View):
    template_name = "cart/cart.html"

    def get(self, request):
        cart = get_cart_for_request(request)
        summary = build_cart_summary(request, cart)

        return render(
            request,
            self.template_name,
            {
                "cart": cart,
                **summary,
            },
        )

class UpdateCartItemView(View):
    def post(self, request, item_id):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)

        try:
            new_quantity = int(request.POST.get("quantity", "1"))
        except (TypeError, ValueError):
            messages.error(request, "تعداد واردشده معتبر نیست.")
            return redirect("cart:cart")

        if new_quantity <= 0:
            return redirect("cart:remove_item", item_id=item_id)

        with transaction.atomic():
            item = (
                CartItem.objects
                .select_for_update()
                .filter(pk=item_id, cart=cart)
                .first()
            )

            if item is None:
                messages.warning(
                    request,
                    "این محصول دیگر در سبد خرید شما نیست."
                )
                return redirect("cart:cart")

            item.quantity = new_quantity
            item.save(update_fields=["quantity"])

            cart.save()

        messages.success(request, "سبد خرید به‌روزرسانی شد.")
        return redirect("cart:cart")


class RemoveCartItemView(View):
    def post(self, request, item_id):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)

        with transaction.atomic():
            item = (
                CartItem.objects
                .select_for_update()
                .filter(pk=item_id, cart=cart)
                .first()
            )

            if item is None:
                messages.warning(
                    request,
                    "این محصول دیگر در سبد خرید شما نیست."
                )
                return redirect("cart:cart")

            item.delete()

        messages.success(request, "محصول از سبد خرید حذف شد.")
        return redirect("cart:cart")


class ApplyCartDiscountView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            messages.info(
                request,
                "برای استفاده از کد تخفیف ابتدا وارد حساب کاربری خود شوید.",
            )
            return redirect("account:login")

        code = request.POST.get("discount_code", "").strip()
        cart = get_cart_for_request(request)

        if not code:
            cart.cart_discount = None
            cart.save(update_fields=["cart_discount"])
            messages.error(request, "لطفاً کد تخفیف را وارد کنید.")
            return redirect("cart:cart")

        discount = Discount.objects.filter(
            code__iexact=code,
            apply_type=Discount.ApplyType.CART,
        ).first()

        if discount is None:
            cart.cart_discount = None
            cart.save(update_fields=["cart_discount"])
            messages.error(request, "کد تخفیف نامعتبر است.")
            return redirect("cart:cart")

        try:
            validate_discount_for_user(discount, request.user)
        except ValidationError as exc:
            Cart.objects.filter(
                pk=cart.pk,
                cart_discount_id=discount.pk,
            ).update(cart_discount=None)

            messages.error(request, " ".join(exc.messages))
            return redirect("cart:cart")

        if not is_discount_available(discount):
            Cart.objects.filter(
                pk=cart.pk,
                cart_discount_id=discount.pk,
            ).update(cart_discount=None)

            messages.error(
                request,
                "کد تخفیف در حال حاضر قابل استفاده نیست یا به سقف مصرف رسیده است.",
            )
            return redirect("cart:cart")

        summary = build_cart_summary(request, cart)

        if not summary["lines"]:
            messages.error(
                request,
                "برای استفاده از کد تخفیف، ابتدا محصولی به سبد خرید اضافه کنید.",
            )
            return redirect("cart:cart")

        minimum = Decimal(str(discount.min_purchase_amount or 0))

        if summary["total_after_product_discount"] < minimum:
            messages.error(
                request,
                f"حداقل مبلغ خرید برای این کد {minimum:,.0f} تومان است.",
            )
            return redirect("cart:cart")

        cart.cart_discount = discount
        cart.save(update_fields=["cart_discount"])

        messages.success(request, "کد تخفیف با موفقیت اعمال شد.")
        return redirect("cart:cart")

@require_GET
def shipping_quote_view(request):
    province = request.GET.get("province", "").strip()

    if not province:
        return JsonResponse(
            {"error": "لطفاً استان را انتخاب کنید."},
            status=400,
        )

    cart = get_cart_for_request(request)
    summary = build_cart_summary(request, cart)

    if not summary["lines"]:
        return JsonResponse(
            {"error": "سبد خرید شما خالی است."},
            status=400,
        )

    shipping_cost = calculate_shipping_cost(province)

    # final_price فعلی در پروژه شما مبلغ پس از تخفیف‌هاست،
    # پس هزینه ارسال را فقط اینجا به آن اضافه می‌کنیم.
    final_price = summary["final_price"] + shipping_cost

    return JsonResponse({
        "shipping_cost": int(shipping_cost),
        "final_price": int(final_price),
    })

class CheckoutView(LoginRequiredMixin, View):
    template_name = "cart/checkout.html"
    login_url = "account:login"

    def get(self, request):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)

        form = CheckoutForm()
        # مقدار پیش‌فرض اولیه بدون استان مشخص
        summary = build_cart_summary(request, cart, province=None)

        if not summary["lines"]:
            messages.info(request, "سبد خرید شما خالی است.")
            return redirect("cart:cart")

        return render(request, self.template_name, {
            "form": form,
            "cart": cart,
            **summary,
        })
    def post(self, request):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)

        form = CheckoutForm(request.POST)
        province = form.cleaned_data.get("province") if form.is_valid() else None

        # محاسبه خلاصه با در نظر گرفتن استان انتخابی کاربر
        summary = build_cart_summary(request, cart, province=province)

        if not summary["lines"]:
            messages.info(request, "سبد خرید شما خالی است.")
            return redirect("cart:cart")

        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "cart": cart,
                **summary,
            })

        with transaction.atomic():
            cart_items = list(
                CartItem.objects.select_for_update().filter(cart=cart).select_related("product", "variant")
            )

            if not cart_items:
                messages.info(request, "سبد خرید شما خالی است.")
                return redirect("cart:cart")

            # محاسبه قطعی نهایی داخل تراکنش با استان معتبر فرم
            province = form.cleaned_data["province"]
            summary = build_cart_summary(request, cart, province=province)

            order = Order.objects.create(
                user=request.user,
                full_name=form.cleaned_data["full_name"],
                phone=form.cleaned_data["phone"],
                address=f"استان: {province} - {form.cleaned_data['address']}",
                postal_code=form.cleaned_data["postal_code"],
                total_price=summary["subtotal"],
                shipping_cost=summary["shipping_cost"],         # ذخیره صحیح هزینه ارسال
                product_discount_amount=summary["product_discount_total"],
                cart_discount_amount=summary["cart_discount_amount"],
                final_price=summary["final_price"],             # شامل مجموع کالاها + ارسال
                cart_discount=summary["cart_discount"],
                status=Order.OrderStatus.PENDING,
            )

            # ایجاد آیتم‌های سفارش
            for line in summary["lines"]:
                OrderItem.objects.create(
                    order=order,
                    variant=line["variant"],
                    product=line["product"],
                    product_title=str(line["product"]),
                    variant_title=(str(line["variant"]) if line["variant"] else ""),
                    unit_price=line["unit_price"],
                    quantity=line["quantity"],
                    total_price=line["line_total"],
                    discount_amount=line["product_discount_amount"],
                )

            if summary["used_product_discount_ids"]:
                Discount.objects.filter(pk__in=summary["used_product_discount_ids"]).update(
                    used_count=F("used_count") + 1)

            if summary["cart_discount"]:
                Discount.objects.filter(pk=summary["cart_discount"].pk).update(used_count=F("used_count") + 1)
                request.session.pop("cart_discount_id", None)

            CartItem.objects.filter(cart=cart).delete()

        messages.success(request, "سفارش شما با موفقیت ثبت شد.")
        return redirect("payment:pay", order_id=order.pk)


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "cart/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        check_and_expire_abandoned_carts()

        orders = list(
            Order.objects
            .filter(user=self.request.user)
            .order_by("-created_at", "-pk")
        )

        # لیست از جدیدترین به قدیمی‌ترین است؛
        # پس شماره قدیمی‌ترین سفارش ۱ و جدیدترین سفارش بزرگ‌ترین عدد می‌شود.
        total_orders = len(orders)

        for index, order in enumerate(orders):
            order.display_number = total_orders - index

        return orders



class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "cart/order_detail.html"
    context_object_name = "order"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


class CancelOrderView(LoginRequiredMixin, View):
    def post(self, request, pk):  # pk همان order_id است که از URL می‌آید
        order = get_object_or_404(Order, pk=pk, user=request.user, status="pending")

        with transaction.atomic():
            for item in order.items.select_related("variant", "product"):
                if item.variant:
                    item.variant.quantity += item.quantity
                    item.variant.save()
                elif item.product:
                    item.product.quantity += item.quantity
                    item.product.save()

            order.status = "cancelled"
            order.save()

        messages.success(request, "سفارش با موفقیت لغو شد و موجودی به انبار بازگشت.")
        return redirect("cart:order_list")


