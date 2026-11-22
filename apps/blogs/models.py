import uuid
from django_ckeditor_5.fields import CKEditor5Field
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.account.models import CustomUser


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="نامک")

    class Meta:
        verbose_name = "دسته‌بندی بلاگ"
        verbose_name_plural = "دسته‌بندی‌های بلاگ"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    title = models.CharField(max_length=100, verbose_name="عنوان برچسب")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="نامک")

    class Meta:
        verbose_name = "برچسب بلاگ"
        verbose_name_plural = "برچسب‌های بلاگ"
        ordering = ["title"]

    def __str__(self):
        return self.title


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشرشده"
        ARCHIVED = "archived", "بایگانی‌شده"

    title = models.CharField(max_length=100, verbose_name="عنوان مقاله")
    slug = models.SlugField(max_length=150, unique=True, blank=True, verbose_name="نامک")
    excerpt = models.CharField(max_length=200, blank=True, verbose_name="خلاصه مقاله")
    content = CKEditor5Field(
        "محتوای مقاله",
        config_name="default",
    )
    cover = models.ImageField(
        upload_to="blog/covers/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="تصویر شاخص",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="posts",
        verbose_name="دسته‌بندی",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="وضعیت انتشار",
    )
    tags = models.ManyToManyField(Tag, related_name="posts", blank=True, verbose_name="برچسب‌ها")
    pub_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="تاریخ انتشار",
        help_text="برای انتشار زمان‌دار، تاریخ آینده وارد کنید.",
    )
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="blog_posts",
        verbose_name="نویسنده",
    )

    meta_title = models.CharField(max_length=60, blank=True, verbose_name="عنوان سئو")
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="توضیحات سئو")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین ویرایش")

    class Meta:
        verbose_name = "مقاله بلاگ"
        verbose_name_plural = "مقاله‌های بلاگ"
        ordering = ["-pub_date", "-id"]
        indexes = [models.Index(fields=["status", "-pub_date"], name="blog_status_pub_idx")]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or "article"
            self.slug = base_slug[:140]
            if BlogPost.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug[:140]}-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title