from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Cart, CartItem, Discount, Order, UserDiscountUsage


ZERO = Decimal("0")


def merge_session_cart_to_user_cart(user, session_key):
    """
    سبد مهمان را به سبد کاربر لاگین‌شده منتقل می‌کند.
    """
    if not session_key:
        return


    with transaction.atomic():
        # ۱. پیدا کردن سبد مهمان
        guest_cart = (
            Cart.objects
            .select_for_update()
            .filter(
                user__isnull=True,
                session_key=session_key,
            )
            .first()
        )


        if not guest_cart:
            return


        # ۲. پیدا کردن یا ساختن سبد اختصاصی کاربر
        user_cart, created = Cart.objects.get_or_create(
            user=user,
            defaults={"session_key": None},
        )


        if guest_cart.pk == user_cart.pk:
            return


        # ۳. انتقال آیتم‌های سبد مهمان به سبد کاربر
        guest_items = CartItem.objects.filter(
            cart=guest_cart
        ).select_related("product", "variant")


        for guest_item in guest_items:
            user_item, item_created = CartItem.objects.get_or_create(
                cart=user_cart,
                product=guest_item.product,
                variant=guest_item.variant,
                defaults={"quantity": guest_item.quantity},
            )


            if not item_created:
                user_item.quantity += guest_item.quantity
                user_item.save(update_fields=["quantity"])


        # ۴. انتقال تخفیف سبد مهمان (اگر کاربر تخفیفی نداشت و خودش قبلاً از آن استفاده نکرده بود)
        if (
            guest_cart.cart_discount_id
            and not user_cart.cart_discount_id
        ):
            # بررسی اینکه آیا کاربر قبلاً از این تخفیف استفاده کرده است یا خیر
            already_used = UserDiscountUsage.objects.filter(
                user=user,
                discount_id=guest_cart.cart_discount_id
            ).exists()

            if not already_used and is_discount_available(guest_cart.cart_discount):
                user_cart.cart_discount_id = guest_cart.cart_discount_id
                user_cart.save(update_fields=["cart_discount"])


        # ۵. پاک کردن سبد مهمان
        guest_cart.delete()


def get_cart_for_request(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            defaults={"session_key": None},
        )
        return cart

    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key

    cart, created = Cart.objects.get_or_create(
        user=None,
        session_key=session_key,
    )

    return cart


def is_discount_available(discount, now=None):
    now = now or timezone.now()

    if not discount.is_active:
        return False

    if discount.active_from and now < discount.active_from:
        return False

    if discount.active_to and now > discount.active_to:
        return False

    if (
        discount.usage_limit is not None
        and discount.used_count >= discount.usage_limit
    ):
        return False

    return True


def validate_discount_for_user(discount, user):
    """
    بررسی می‌کند که آیا کاربر مجاز به استفاده از این کد تخفیف است یا خیر.
    هر کاربر فقط یک‌بار می‌تواند از یک کد تخفیف سبد استفاده کند.
    """
    if not user.is_authenticated:
        raise ValidationError("برای استفاده از کد تخفیف باید وارد حساب کاربری خود شوید.")

    already_used = UserDiscountUsage.objects.filter(
        user=user,
        discount=discount
    ).exists()

    if already_used:
        raise ValidationError("شما قبلاً از این کد تخفیف استفاده کرده‌اید و هر کاربر تنها یک‌بار مجاز به استفاده از آن است.")

    if not is_discount_available(discount):
        raise ValidationError("این کد تخفیف منقضی شده یا به سقف مصرف رسیده است.")

    return True


def calculate_discount_amount(discount, base_amount):
    base_amount = Decimal(str(base_amount or 0))
    value = Decimal(str(discount.value or 0))

    if base_amount <= ZERO or value <= ZERO:
        return ZERO

    if discount.discount_type == Discount.DiscountType.PERCENTAGE:
        amount = base_amount * value / Decimal("100")

        if discount.max_discount_amount is not None:
            cap = Decimal(str(discount.max_discount_amount))
            amount = min(amount, cap)

    else:  # مبلغ ثابت
        amount = min(value, base_amount)

    amount = min(amount, base_amount)
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def get_unit_price(product, variant):
    if variant and variant.product_id == product.pk:
        return Decimal(str(variant.price))

    return Decimal(str(product.price))


def get_product_discount(product, line_subtotal, now=None):
    now = now or timezone.now()
    line_subtotal = Decimal(str(line_subtotal or 0))

    discounts = Discount.objects.filter(
        apply_type=Discount.ApplyType.PRODUCT,
        is_active=True,
    )

    best_discount = None
    best_amount = ZERO

    for discount in discounts:
        if not is_discount_available(discount, now=now):
            continue

        if discount.products.exists() and not discount.products.filter(
            pk=product.pk
        ).exists():
            continue

        minimum = Decimal(str(discount.min_purchase_amount or 0))
        if line_subtotal < minimum:
            continue

        amount = calculate_discount_amount(discount, line_subtotal)

        if amount > best_amount:
            best_discount = discount
            best_amount = amount

    return best_discount, best_amount


def get_cart_discount(cart, now=None):
    """
    تخفیف سبد را از فیلد cart.cart_discount می‌خواند.
    اگر منقضی شده باشد، کاربر قبلاً استفاده کرده باشد یا معتبر نباشد،
    به‌صورت خودکار آن را از روی سبد پاک کرده و None برمی‌گرداند.
    """
    now = now or timezone.now()
    discount = cart.cart_discount

    if not discount:
        return None

    if discount.apply_type != Discount.ApplyType.CART:
        cart.cart_discount = None
        cart.save(update_fields=["cart_discount"])
        return None

    if not is_discount_available(discount, now=now):
        cart.cart_discount = None
        cart.save(update_fields=["cart_discount"])
        return None

    if cart.user_id:
        if UserDiscountUsage.objects.filter(user_id=cart.user_id, discount_id=discount.pk).exists():
            cart.cart_discount = None
            cart.save(update_fields=["cart_discount"])
            return None

    return discount


def calculate_shipping_cost(province):
    # مثال: استان‌های دورتر یا کلان‌شهرها هزینه متفاوتی دارند
    # اگر استان تهران بود ۵۰ هزار تومان، سایر استان‌ها ۹۰ هزار تومان (به تومان)
    if not province:
        return Decimal("0")

    if province.strip() in ["تهران", "البرز"]:
        return Decimal("150000")
    else:
        return Decimal("300000")
def build_cart_summary(request, cart, province=None):
    now = timezone.now()

    lines = []
    subtotal = ZERO
    product_discount_total = ZERO
    used_product_discount_ids = set()

    cart_items = CartItem.objects.filter(cart=cart).select_related(
        "product",
        "variant",
    )

    for item in cart_items:
        quantity = int(item.quantity)
        unit_price = get_unit_price(item.product, item.variant)
        line_subtotal = unit_price * quantity

        product_discount, line_discount = get_product_discount(
            item.product,
            line_subtotal,
            now=now,
        )

        line_total = line_subtotal - line_discount

        subtotal += line_subtotal
        product_discount_total += line_discount

        if product_discount:
            used_product_discount_ids.add(product_discount.pk)

        lines.append({
            "item": item,
            "product": item.product,
            "variant": item.variant,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_subtotal": line_subtotal,
            "product_discount": product_discount,
            "product_discount_amount": line_discount,
            "line_total": line_total,
        })

    total_after_product_discount = subtotal - product_discount_total

    # محاسبه تخفیف سبد خرید (کپن)
    cart_discount = get_cart_discount(cart, now=now)
    cart_discount_amount = ZERO

    if cart_discount:
        minimum = Decimal(str(cart_discount.min_purchase_amount or 0))
        if total_after_product_discount >= minimum:
            if cart_discount.discount_type == Discount.DiscountType.PERCENTAGE:
                cart_discount_amount = (total_after_product_discount * cart_discount.value) / Decimal("100")
                if cart_discount.max_discount_amount and cart_discount_amount > cart_discount.max_discount_amount:
                    cart_discount_amount = cart_discount.max_discount_amount
            elif cart_discount.discount_type == Discount.DiscountType.FIXED:
                cart_discount_amount = cart_discount.value

            if cart_discount_amount > total_after_product_discount:
                cart_discount_amount = total_after_product_discount

    net_product_price = total_after_product_discount - cart_discount_amount
    if net_product_price < ZERO:
        net_product_price = ZERO

    # محاسبه هزینه ارسال بر اساس استان انتخابی
    shipping_cost = calculate_shipping_cost(province)

    # مبلغ نهایی کل (محصولات پس از تخفیف + هزینه ارسال)
    final_price = net_product_price + shipping_cost

    return {
        "lines": lines,
        "subtotal": subtotal,
        "product_discount_total": product_discount_total,
        "total_after_product_discount": total_after_product_discount,
        "cart_discount": cart_discount,
        "cart_discount_amount": cart_discount_amount,
        "shipping_cost": shipping_cost,
        "final_price": final_price,
        "used_product_discount_ids": used_product_discount_ids,
    }



def restore_stock_for_cart_items(cart_items):
    for item in cart_items:
        if item.variant:
            item.variant.quantity += item.quantity
            item.variant.save(update_fields=["quantity"])
        elif item.product:
            item.product.quantity += item.quantity
            item.product.save(update_fields=["quantity"])


def check_and_expire_abandoned_carts():
    expiration_limit = timezone.now() - timedelta(hours=24)
    Cart.objects.filter(
        user__isnull=True,
        updated_at__lt=expiration_limit,
    ).delete()
