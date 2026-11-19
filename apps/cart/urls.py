from django.urls import path
from .views import (
    CartView,
    UpdateCartItemView,
    RemoveCartItemView,
    ApplyCartDiscountView,
    CheckoutView,
    OrderListView,
    OrderDetailView,
AddToCartView,
)

app_name = "cart"

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("item/<int:item_id>/update/", UpdateCartItemView.as_view(), name="update_cart_item"),
    path("item/<int:item_id>/remove/", RemoveCartItemView.as_view(), name="remove_from_cart"),
    path("apply-discount/", ApplyCartDiscountView.as_view(), name="apply_discount"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("my-orders/", OrderListView.as_view(), name="order_list"),
    path("my-orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
path("add/<int:product_id>/", AddToCartView.as_view(), name="add_to_cart"),

]
