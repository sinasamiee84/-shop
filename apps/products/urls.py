from django.urls import path

from .views import (
    CategoryDetailView,
    ProductDetailView,
    ProductListView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("category/<str:slug>/", CategoryDetailView.as_view(), name="category_detail"),
    path("product/<str:slug>/", ProductDetailView.as_view(), name="detail"),
]
