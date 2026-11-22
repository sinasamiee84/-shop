from django.utils import timezone
from django.views.generic import ListView, DetailView

from .models import BlogPost


def public_posts():
    """
    فقط مقاله‌هایی را برمی‌گرداند که منتشر شده‌اند
    و زمان انتشارشان رسیده است.
    """
    return BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        pub_date__lte=timezone.now(),
    )


class BlogHomeView(ListView):
    model = BlogPost
    context_object_name = "blog_posts"
    template_name = "blogs/home.html"

    def get_queryset(self):
        return public_posts().select_related(
            "category",
            "author",
        ).order_by("-pub_date")[:4]


class BlogPostListView(ListView):
    model = BlogPost
    context_object_name = "blog_posts"
    template_name = "blogs/list.html"
    paginate_by = 4

    def get_queryset(self):
        return public_posts().select_related(
            "category",
            "author",
        ).prefetch_related("tags").order_by("-pub_date")


class BlogPostDetailView(DetailView):
    model = BlogPost
    context_object_name = "blog_post"
    template_name = "blogs/detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return public_posts().select_related(
            "category",
            "author",
        ).prefetch_related("tags")
