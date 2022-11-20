from django.urls import path, re_path

from .views import invoice_view


urlpatterns = [
    path('', invoice_view, name='invoice'),
]