from django.db import models
from django.contrib import admin
from .models import *


class InvoiceTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description']


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['mftuser', 'invoice_type', 'created_by', 'created_at']
    list_filter = ['mftuser']
    ordering = ['mftuser']


admin.site.register(InvoiceType, InvoiceTypeAdmin)
admin.site.register(Invoice, InvoiceAdmin)