from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView

from apps.products.models import Category, Product
from django.db.models import Prefetch
from apps.products.models import Category, Product, ProductVariant

def get_category_sections():
    """هر دسته‌بندی همراه با حداکثر ۸ محصول فعال آن."""
    sections = []

    for category in Category.objects.order_by("name"):
        products = list(
            Product.objects.filter(category=category, is_active=True)
            .prefetch_related("images")
            .order_by("-created_at", "-pk")[:8]
        )
        sections.append({
            "category": category,
            "products": products,
        })

    return sections


class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # حالا این باید در ترمینال چاپ شود
        print("--- DEBUG: HomePageView is working! ---")

        products = Product.objects.filter(is_active=True).prefetch_related("images").order_by("-created_at")[:8]
        context["recent_products"] = products
        return context

class ProductListView(TemplateView):
    # این صفحه «لیست دسته‌بندی‌ها» است، نه لیست یک‌تکهٔ همهٔ محصولات.
    template_name = "products/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories_with_products"] = get_category_sections()
        return context


class CategoryDetailView(ListView):
    model = Product
    template_name = "products/category_detail.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        self.category = get_object_or_404(
            Category,
            slug=self.kwargs["slug"],
        )
        return (
            Product.objects.filter(category=self.category, is_active=True)
            .prefetch_related("images")
            .order_by("-created_at", "-pk")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = "products/detail.html"
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("category", "brand", "model")
            .prefetch_related(
                "images",
                Prefetch(
                    "variants",
                    queryset=ProductVariant.objects
                    .select_related("color")
                    .order_by("pk"),
                ),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        variants = [
            {
                "id": variant.id,
                "color_id": variant.color_id,
                "color_name": variant.color.name if variant.color else "بدون رنگ",
                "size": variant.size or "",
                "size_name": variant.get_size_display() if variant.size else "بدون سایز",
                "price": str(variant.price),
                "quantity": variant.quantity,
            }
            for variant in self.object.variants.all()
        ]

        context["variants_data"] = variants
        context["initial_variant"] = next(
            (variant for variant in variants if variant["quantity"] > 0),
            variants[0] if variants else None,
        )
        return context