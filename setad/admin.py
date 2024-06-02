from django.contrib import admin

from .models import *


class SetadUserInvoiceAdmin(admin.ModelAdmin):
    list_display = ['serial_number', 'get_jalali_created_at', 'username', 'group_type', 'department', 'all_business']
    list_filter = ['group_type', 'department']
    # ordering = ['serial_number', 'username', 'group_type', 'department']
    search_fields = ['firstname', 'lastname', 'username', 'group_type', 'department', 'all_business']


class AzmoonDirectoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'absolute_path', 'index_code', 'created_by']
    list_filter = ['index_code__code', 'business']
    search_fields = ['absolute_path']
    ordering = ['absolute_path']


class AzmoonDirectoryPermissionAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'directory', 'permission', 'is_confirmed']
    list_filter = ['invoice']
    search_fields = ['invoice__username', 'invoice__business__code']
    # ordering = ['absolute_path']


admin.site.register(SetadUserInvoice, SetadUserInvoiceAdmin)
admin.site.register(AzmoonDirectory, AzmoonDirectoryAdmin)
admin.site.register(AzmoonDirectoryPermission, AzmoonDirectoryPermissionAdmin)