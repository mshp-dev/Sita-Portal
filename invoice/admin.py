from django.db import models
from django.contrib import admin
from .models import *


class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['mftuser', 'created_by', 'created_at']


admin.site.register(Invoice, InvoiceAdmin)