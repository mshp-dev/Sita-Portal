from django.db import models
from django.contrib import admin
from .models import *


class InvoiceTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'serial_prefix', 'description']


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_type', 'get_mftuser', 'serial_number', 'created_by', 'created_at']
    list_filter = ['created_by']
    ordering = ['mftuser', 'created_at', 'created_by']


class PreInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_type', 'directories_list', 'serial_number', 'created_by', 'created_at']
    list_filter = ['created_by']
    ordering = ['created_at', 'created_by']


admin.site.register(InvoiceType, InvoiceTypeAdmin)
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(PreInvoice, PreInvoiceAdmin)