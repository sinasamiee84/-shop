from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView
from django.db.models import F
from .forms import CheckoutForm
from .models import CartItem, Order, OrderItem, Product, ProductVariant, Discount,Cart
from .services import (
    build_cart_summary,
    get_cart_for_request,
    check_and_expire_abandoned_carts,
)
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.http import JsonResponse  # حتماً این را در بالا ایمپورت کنید


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
        # بررسی سبدهای منقضی‌شده
        check_and_expire_abandoned_carts()

        # دریافت محصول
        product = get_object_or_404(Product, pk=product_id)

        # دریافت شناسه واریانت
        variant_id = request.POST.get("variant_id")

        # در صورت داشتن فیلد quantity، مقدار آن را می‌خوانیم
        # در غیر این صورت، هر بار یک عدد اضافه می‌شود
        try:
            requested_quantity = int(
                request.POST.get("quantity", "1")
            )
        except (TypeError, ValueError):
            requested_quantity = 1

        if requested_quantity < 1:
            requested_quantity = 1

        # دریافت سبد خرید فعلی کاربر یا مهمان
        cart = get_cart_for_request(request)

        try:
            with transaction.atomic():
                # قفل کردن رکورد سبد برای جلوگیری از ثبت همزمان
                cart = Cart.objects.select_for_update().get(
                    pk=cart.pk
                )

                # قفل کردن محصول
                product = Product.objects.select_for_update().get(
                    pk=product_id
                )

                variant = None

                # اگر محصول واریانت دارد، همان واریانت را قفل می‌کنیم
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant.objects.select_for_update(),
                        pk=variant_id,
                        product_id=product.id,
                    )

                    available_quantity = variant.quantity

                else:
                    # محصول ساده
                    available_quantity = product.quantity

                # بررسی موجودی
                if available_quantity < requested_quantity:
                    redirect_url = product_url_with_variant(
                        product,
                        variant_id
                    )

                    if variant:
                        messages.error(
                            request,
                            (
                                "موجودی این واریانت کافی نیست. "
                                f"موجودی فعلی: {available_quantity} عدد"
                            )
                        )
                    else:
                        messages.error(
                            request,
                            (
                                "موجودی محصول کافی نیست. "
                                f"موجودی فعلی: {available_quantity} عدد"
                            )
                        )

                    return redirect(redirect_url)

                # پیدا کردن یا ساختن آیتم سبد
                cart_item, created = (
                    CartItem.objects
                    .select_for_update()
                    .get_or_create(
                        cart=cart,
                        product=product,
                        variant=variant,
                        defaults={
                            "quantity": 0
                        }
                    )
                )

                # کسر موجودی دقیقاً به اندازه تعداد درخواستی
                if variant:
                    variant.quantity -= requested_quantity
                    variant.save(
                        update_fields=["quantity"]
                    )
                else:
                    product.quantity -= requested_quantity
                    product.save(
                        update_fields=["quantity"]
                    )

                # اضافه کردن تعداد به سبد
                cart_item.quantity += requested_quantity
                cart_item.save(
                    update_fields=["quantity"]
                )

                # به‌روزرسانی زمان آخرین فعالیت سبد
                cart.save()

        except ProductVariant.DoesNotExist:
            messages.error(
                request,
                "واریانت انتخاب‌شده معتبر نیست."
            )

            return redirect(
                product.get_absolute_url()
            )

        # ساخت آدرس بازگشت همراه با واریانت انتخاب‌شده
        redirect_url = product_url_with_variant(
            product,
            variant_id
        )

        messages.success(
            request,
            "محصول با موفقیت به سبد خرید اضافه شد."
        )

        return redirect(redirect_url)


class CartView(View):
    template_name = "cart/cart.html"

    def get(self, request):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)
        summary = build_cart_summary(request, cart)
        return render(request, self.template_name, {"cart": cart, **summary})


class UpdateCartItemView(View):
    def post(self, request, item_id):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)
        item = get_object_or_404(
            CartItem.objects.select_related("product", "variant"),
            pk=item_id,
            cart=cart
        )

        try:
            new_quantity = int(request.POST.get("quantity", "1"))
        except (TypeError, ValueError):
            messages.error(request, "تعداد واردشده معتبر نیست.")
            return redirect("cart:cart")

        with transaction.atomic():
            diff = new_quantity - item.quantity

            if diff > 0:  # تعداد افزایش یافته -> کسر مابه‌التفاوت از انبار
                available = item.variant.quantity if item.variant else item.product.quantity
                if available < diff:
                    messages.error(request, "موجودی انبار برای این تعداد کافی نیست.")
                    return redirect("cart:cart")

                if item.variant:
                    item.variant.quantity -= diff
                    item.variant.save(update_fields=["quantity"])
                else:
                    item.product.quantity -= diff
                    item.product.save(update_fields=["quantity"])

            elif diff < 0:  # تعداد کاهش یافته -> بازگرداندن مابه‌التفاوت به انبار
                return_qty = abs(diff)
                if item.variant:
                    item.variant.quantity += return_qty
                    item.variant.save(update_fields=["quantity"])
                else:
                    item.product.quantity += return_qty
                    item.product.save(update_fields=["quantity"])

            if new_quantity <= 0:
                item.delete()
                messages.success(request, "محصول از سبد خرید حذف شد.")
            else:
                item.quantity = new_quantity
                item.save(update_fields=["quantity"])
                messages.success(request, "سبد خرید به‌روزرسانی شد.")

            cart.save()

        return redirect("cart:cart")


class RemoveCartItemView(View):
    def post(self, request, item_id):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)
        item = get_object_or_404(
            CartItem.objects.select_related("product", "variant"),
            pk=item_id,
            cart=cart
        )

        with transaction.atomic():
            # بازگرداندن کل موجودی این آیتم به انبار هنگام حذف از سبد
            if item.variant:
                item.variant.quantity += item.quantity
                item.variant.save(update_fields=["quantity"])
            else:
                item.product.quantity += item.quantity
                item.product.save(update_fields=["quantity"])

            item.delete()
            cart.save()

        messages.success(request, "محصول از سبد خرید حذف شد.")
        return redirect("cart:cart")


class ApplyCartDiscountView(View):
    def post(self, request):
        code = request.POST.get("discount_code", "").strip()
        if not code:
            messages.error(request, "لطفاً کد تخفیف را وارد کنید.")
            return redirect("cart:cart")

        try:
            discount = Discount.objects.get(code__iexact=code, apply_type="cart", is_active=True)
            request.session["cart_discount_id"] = discount.pk
            messages.success(request, "کد تخفیف اعمال شد.")
        except Discount.DoesNotExist:
            messages.error(request, "کد تخفیف معتبر نیست یا منقضی شده است.")

        return redirect("cart:cart")


class CheckoutView(LoginRequiredMixin, View):
    template_name = "cart/checkout.html"
    login_url = "account:login"

    def get(self, request):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)
        summary = build_cart_summary(request, cart)

        if not summary["lines"]:
            messages.info(request, "سبد خرید شما خالی است.")
            return redirect("cart:cart")

        form = CheckoutForm()
        return render(request, self.template_name, {"form": form, "cart": cart, **summary})

    def post(self, request):
        check_and_expire_abandoned_carts()
        cart = get_cart_for_request(request)
        summary = build_cart_summary(request, cart)

        if not summary["lines"]:
            messages.info(request, "سبد خرید شما خالی است.")
            return redirect("cart:cart")

        form = CheckoutForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "cart": cart, **summary})

        with transaction.atomic():
            cart_items = list(
                CartItem.objects.select_for_update()
                .filter(cart=cart)
                .select_related("product", "variant")
            )

            if not cart_items:
                messages.info(request, "سبد خرید شما خالی است.")
                return redirect("cart:cart")

            summary = build_cart_summary(request, cart)

            # ثبت سفارش نهایی (چون موجودی قبلاً در زمان افزودن به سبد کم شده بود، نیاز به کسر مجدد نیست)
            order = Order.objects.create(
                user=request.user,
                full_name=form.cleaned_data["full_name"],
                phone=form.cleaned_data["phone"],
                postal_code=form.cleaned_data["postal_code"],
                address=form.cleaned_data["address"],
                total_price=summary["subtotal"],
                product_discount_amount=summary["product_discount_total"],
                cart_discount_amount=summary["cart_discount_amount"],
                final_price=summary["final_price"],
                status="pending",  # یا پرداخت شده
            )

            for line in summary["lines"]:
                OrderItem.objects.create(
                    order=order,
                    product=line["product"],
                    variant=line["variant"],
                    product_title=str(line["product"]),
                    variant_title=str(line["variant"]) if line["variant"] else "",
                    unit_price=line["unit_price"],
                    quantity=line["quantity"],
                    total_price=line["line_total"],
                    discount_amount=line["product_discount_amount"],
                )

            # آپدیت تعداد استفاده از تخفیف‌ها
            if summary["used_product_discount_ids"]:
                Discount.objects.filter(pk__in=summary["used_product_discount_ids"]).update(
                    used_count=F("used_count") + 1
                )
            if summary["cart_discount"]:
                Discount.objects.filter(pk=summary["cart_discount"].pk).update(
                    used_count=F("used_count") + 1
                )
                request.session.pop("cart_discount_id", None)

            # پاکسازی آیتم‌های سبد خرید (بدون بازگشت به انبار، چون سفارش ثبت شد)
            CartItem.objects.filter(cart=cart).delete()

        messages.success(request, "سفارش شما با موفقیت ثبت شد.")
        return redirect("cart:order_detail", pk=order.pk)


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "cart/order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        check_and_expire_abandoned_carts()
        return Order.objects.filter(user=self.request.user).order_by("-created_at")


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = "cart/order_detail.html"
    context_object_name = "order"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")
