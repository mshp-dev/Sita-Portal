from django.urls import path, re_path

from .views import *
# (
#     invoice_create_view,
#     invoice_confirm_view,
#     invoice_reject_view,
#     invoice_delete_view,
#     invoice_update_view,
#     invoice_details_view,
#     invoices_list_view
# )


urlpatterns = [
    path('create/', invoice_create_view, name='invoice-create'),
    path('confirm/<int:iid>/', invoice_confirm_view, name='invoice-confirm'),
    path('reject/<int:iid>/', invoice_reject_view, name='invoice-reject'),
    path('delete/<int:iid>/', invoice_delete_view, name='invoice-delete'),
    path('update/<int:iid>/', invoice_update_view, name='invoice-update'),
    path('details/<int:iid>/', invoice_details_view, name='invoice-details'),
    path('get-permissions/<int:iid>/', invoice_get_permissions_view, name='invoice-permissions'),
    path('list/', invoices_list_view, name='invoices-list'),
]