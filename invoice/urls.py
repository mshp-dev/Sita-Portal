from django.urls import path, re_path

from .views import invoice_create_view, invoices_list_view


urlpatterns = [
    path('create/', invoice_create_view, name='invoice-create'),
    path('list/', invoices_list_view, name='invoices-list'),
]