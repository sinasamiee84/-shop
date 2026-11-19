from django.urls import path
from . import views

app_name = "payment"

urlpatterns = [
    path("pay/<int:order_id>/", views.start_payment, name="pay"),
    path("verify/", views.verify_payment, name="verify"),
]
