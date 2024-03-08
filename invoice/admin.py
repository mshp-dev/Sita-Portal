from django.contrib import admin
from .models import *


class InvoiceTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'serial_prefix', 'description']


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_type', 'mftuser', 'serial_number', 'description', 'created_by', 'get_jalali_created_at', 'confirm_or_reject']
    list_filter = ['invoice_type', 'confirm_or_reject', 'created_by']
    ordering = ['mftuser__username', 'created_at', 'created_by']
    search_fields = ['mftuser__username', 'serial_number']


class PreInvoiceAdmin(admin.ModelAdmin):
    list_display = ['get_list_of_directories', 'serial_number', 'description', 'created_by', 'get_jalali_created_at', 'confirm_or_reject']
    list_filter = ['confirm_or_reject', 'created_by']
    ordering = ['created_at', 'created_by']
    search_fields = ['serial_number']


admin.site.register(InvoiceType, InvoiceTypeAdmin)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(PreInvoice, PreInvoiceAdmin)