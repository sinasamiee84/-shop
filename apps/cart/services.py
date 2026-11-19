from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .models import Cart, CartItem, Discount, Order

ZERO = Decimal("0")


def merge_session_cart_to_user_cart(request, user):
    """
    سبد خرید موجود در سشن را با سبد خرید کاربر پس از لاگین ادغام می‌کند.
    """
    session_cart_id = request.session.get("cart_id")
    if not session_cart_id:
        return

    try:
        session_cart = Cart.objects.get(id=session_cart_id, user__isnull=True)
    except Cart.DoesNotExist:
        return

    user_cart, created = Cart.objects.get_or_create(user=user)

    if session_cart == user_cart:
        return

    for session_item in session_cart.items.all():
        user_item, item_created = CartItem.objects.get_or_create(
            cart=user_cart,
            product=session_item.product,
            variant=session_item.variant,
            defaults={"quantity": session_item.quantity}
        )
        if not item_created:
            user_item.quantity += session_item.quantity
            user_item.save(update_fields=["quantity"])

    session_cart.delete()
    request.session["cart_id"] = str(user_cart.id)
    request.session.modified = True


def get_cart_for_request(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        if "cart_id" in request.session:
            del request.session["cart_id"]
        return cart

    cart_id = request.session.get("cart_id")
    if cart_id:
        try:
            return Cart.objects.get(id=cart_id, user__isnull=True)
        except Cart.DoesNotExist:
            pass

    cart = Cart.objects.create(user=None)
    request.session["cart_id"] = str(cart.id)
    return cart


def get_unit_price(product, variant=None):
    if variant is not None:
        variant_price = getattr(variant, "price", None)
        if variant_price is not None:
            return Decimal(str(variant_price))
    return Decimal(str(product.price))


def is_discount_available(discount, now=None):
    now = now or timezone.now()
    if not discount.is_active:
        return False
    if discount.active_from and discount.active_from > now:
        return False
    if discount.active_to and discount.active_to < now:
        return False
    if discount.usage_limit is not None and discount.used_count >= discount.usage_limit:
        return False
    return True


def calculate_discount_amount(discount, amount):
    amount = max(Decimal(str(amount)), ZERO)
    value = max(Decimal(str(discount.value)), ZERO)

    if str(discount.discount_type).lower() in {"percent", "percentage"}:
        discount_amount = amount * value / Decimal("100")
    else:
        discount_amount = value
    return min(discount_amount, amount)


def get_product_discount(product, unit_price, now=None):
    now = now or timezone.now()
    best_discount = None
    best_amount = ZERO

    discounts = Discount.objects.filter(
        is_active=True,
        apply_type="product",
        products=product,
    ).distinct()

    for discount in discounts:
        if not is_discount_available(discount, now=now):
            continue
        amount = calculate_discount_amount(discount, unit_price)
        if amount > best_amount:
            best_discount = discount
            best_amount = amount

    return best_discount, best_amount


def get_cart_discount(request, now=None):
    discount_id = request.session.get("cart_discount_id")
    if not discount_id:
        return None
    try:
        discount = Discount.objects.get(pk=discount_id)
    except (Discount.DoesNotExist, TypeError, ValueError):
        request.session.pop("cart_discount_id", None)
        return None

    if discount.apply_type != "cart" or not is_discount_available(discount, now=now):
        request.session.pop("cart_discount_id", None)
        return None

    return discount


def build_cart_summary(request, cart):
    now = timezone.now()
    lines = []
    subtotal = ZERO
    product_discount_total = ZERO
    used_product_discount_ids = set()

    cart_items = CartItem.objects.filter(cart=cart).select_related("product", "variant")

    for item in cart_items:
        quantity = int(item.quantity)
        unit_price = get_unit_price(item.product, item.variant)
        line_subtotal = unit_price * quantity

        product_discount, unit_discount = get_product_discount(item.product, unit_price, now=now)
        line_discount = unit_discount * quantity
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
    cart_discount = get_cart_discount(request, now=now)
    cart_discount_amount = ZERO

    if cart_discount:
        minimum = Decimal(str(cart_discount.min_purchase_amount or 0))
        if total_after_product_discount >= minimum:
            cart_discount_amount = calculate_discount_amount(cart_discount, total_after_product_discount)

    final_price = max(total_after_product_discount - cart_discount_amount, ZERO)

    return {
        "lines": lines,
        "subtotal": subtotal,
        "product_discount_total": product_discount_total,
        "total_after_product_discount": total_after_product_discount,
        "cart_discount": cart_discount,
        "cart_discount_amount": cart_discount_amount,
        "final_price": final_price,
        "used_product_discount_ids": used_product_discount_ids,
    }


def restore_stock_for_cart_items(cart_items):
    """
    موجودی اقلام داخل سبد خرید را به انبار برمی‌گرداند (هنگام حذف یا انقضای ۲۴ ساعته سبد).
    """
    for item in cart_items:
        if item.variant:
            item.variant.quantity += item.quantity
            item.variant.save(update_fields=["quantity"])
        elif item.product:
            item.product.quantity += item.quantity
            item.product.save(update_fields=["quantity"])


def check_and_expire_abandoned_carts():
    """
    سبدهای خریدی که بیش از ۲۴ ساعت از آخرین ویرایش آن‌ها گذشته و پرداخت نشده‌اند را
    منقضی کرده و موجودی‌شان را به انبار بازمی‌گرداند.
    """
    expiration_limit = timezone.now() - timedelta(hours=24)
    expired_carts = Cart.objects.filter(
        updated_at__lt=expiration_limit
    ).prefetch_related("items__product", "items__variant")

    for cart in expired_carts:
        with transaction.atomic():
            restore_stock_for_cart_items(cart.items.all())
            cart.items.all().delete()
