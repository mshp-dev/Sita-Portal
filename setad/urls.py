from django.urls import path, re_path

from .views import *


urlpatterns = [
    path('create-user/', setad_user_create_view, name='setad-user-create'),
    path('invoices/', manage_setad_user_invoice_view, name='setad-user-management'),
    path('invoice/details/<int:iid>/', setad_user_invoice_view, name='setad-user-invoice-details'),
    path('invoice/confirm/<int:iid>/', setad_user_invoice_confirm_view, name='setad-user-invoice-confirm'),
    # path('invoice/reject/<int:iid>/', setad_user_invoice_reject_view, name='setad-user-invoice-reject'),
    path('invoice/delete/<int:iid>/', setad_user_invoice_delete_view, name='setad-user-invoice-delete'),
    path('invoice/update/<int:iid>/', setad_user_invoice_update_view, name='setad-user-invoice-update'),
]