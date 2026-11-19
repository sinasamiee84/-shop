from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.products.views import HomePageView
urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('account/', include('apps.account.urls', namespace='account')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('cart/', include('apps.cart.urls', namespace='cart')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
