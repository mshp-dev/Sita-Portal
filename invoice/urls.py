from django.urls import path, re_path

from .views import invoice_create_view, invoice_delete_view, invoice_details_view, invoices_list_view


urlpatterns = [
    path('create/', invoice_create_view, name='invoice-create'),
    path('delete/<int:iid>/', invoice_delete_view, name='invoice-delete'),
    path('details/<int:iid>/', invoice_details_view, name='invoice-details'),
    path('list/', invoices_list_view, name='invoices-list'),
]