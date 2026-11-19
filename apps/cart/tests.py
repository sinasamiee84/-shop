from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.account.models import CustomUser
from apps.products.models import Brand, BrandModel, Category, Product, Color
from apps.cart.models import Cart, CartItem, Discount


class CartDiscountTestCase(TestCase):
    def setUp(self):
        # ۱. ایجاد کاربر با فیلد درست
        self.user = CustomUser.objects.create_user(
            phone_number="09123456789",
            password="password123"
        )

        # ۲. ایجاد وابستگی‌های لازم برای Product
        self.brand = Brand.objects.create(name="برند تست", country="ایران")
        self.brand_model = BrandModel.objects.create(brand=self.brand, name="مدل تست")
        self.category = Category.objects.create(name="دسته‌بندی تست")
        self.color = Color.objects.create(name="قرمز")

        # ۳. ایجاد محصول با فیلدهای واقعی مدل شما
        self.product = Product.objects.create(
            title="تست محصول",
            price=Decimal("1000000"),
            quantity=10,
            category=self.category,
            brand=self.brand,
            model=self.brand_model,
            color=self.color,
            is_active=True
        )

        # ۴. ایجاد تخفیف بر اساس مدل شما
        self.discount = Discount.objects.create(
            code="OFF100",
            title="تخفیف ۱۰۰ تومانی",
            discount_type=Discount.DiscountType.FIXED,
            apply_type=Discount.ApplyType.CART,
            value=Decimal("100000"),
            min_purchase_amount=Decimal("500000"),
            is_active=True,
            active_from=timezone.now() - timedelta(days=1),
            active_to=timezone.now() + timedelta(days=1),
            usage_limit=10
        )

    def test_apply_valid_discount_view(self):
        self.client.login(phone_number="09123456789", password="password123")

        # ساخت سبد خرید برای کاربر
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        # ارسال POST به ویو
        response = self.client.post(reverse('cart:apply_discount'), {'discount_code': 'OFF100'})

        # بررسی ریدایرکت (302) و ذخیره در سشن
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('cart_discount_id'), self.discount.id)

    def test_expired_discount_rejection(self):
        # منقضی کردن تخفیف
        self.discount.active_to = timezone.now() - timedelta(days=1)
        self.discount.save()

        self.client.login(phone_number="09123456789", password="password123")

        response = self.client.post(reverse('cart:apply_discount'), {'discount_code': 'OFF100'})

        # بررسی اینکه تخفیف اعمال نشود
        self.assertNotIn('cart_discount_id', self.client.session)
