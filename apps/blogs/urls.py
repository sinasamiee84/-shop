from django.urls import path
from . import views
app_name = 'blogs'

urlpatterns = [
    path('', views.BlogHomeView.as_view(), name='blog_home'),
    path('list', views.BlogPostListView.as_view(), name='list'),
    path('detail/<slug:slug>', views.BlogPostDetailView.as_view(), name='detail'),

]