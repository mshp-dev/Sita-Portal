from django.db import models
from django.contrib import admin
from .models import *


class CodingTypeAdmin(admin.ModelAdmin):
    list_display = ['type', 'description']


class BusinessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'address']
    list_filter = ['address']
    ordering = ['description']


class BankIdentifierCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']
    ordering = ['description']


class IscUserAccessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class IscDepartmentCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id', 'access_type']


class DirectoryPermissionCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'value', 'type_id']
    ordering = ['value']


class CustomerAccessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class CustomerAccessTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class DirectoryIndexCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class IscUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department']
    list_filter = ['role', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering = ['user__username']


class MftUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'mobilephone', 'organization', 'get_all_business', 'ipaddr', 'created_by', 'is_confirmed']
    list_filter = ['organization', 'business']
    search_fields = ('username', 'firstname', 'lastname')
    ordering = ['username']


class MftUserTempAdmin(admin.ModelAdmin):
    list_display = ['username', 'mobilephone', 'organization', 'get_all_business', 'ipaddr', 'created_by', 'is_confirmed']
    list_filter = ['organization', 'business']
    search_fields = ('username', 'firstname', 'lastname')
    ordering = ['username']

class DirectoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'absolute_path', 'bic', 'index_code']
    list_filter = ['bic', 'business']
    search_fields = ['relative_path', 'bic__description', 'business__description']
    ordering = ['name']


class PermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'directory_path', 'permission']
    list_filter = ['permission', 'directory__bic', 'directory__business']
    search_fields = ['user__username', 'directory__name', 'permission']
    ordering = ['user__username']


# class CustomerAccessAdmin(admin.ModelAdmin):
#     list_display = ['user', 'access_on_bic']


class OperationBusinessAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_department', 'access_on_bus', 'owned_by_user']
    list_filter = ['user__department', 'access_on_bus']
    search_fields = ['user__user__username', 'access_on_bus__description']
    ordering = ['user']


class CustomerBankAdmin(admin.ModelAdmin):
    list_display = ['user', 'access_on_bic']
    list_filter = ['user__department', 'access_on_bic']
    search_fields = ['user__user__username', 'access_on_bic__description']
    ordering = ['user']


class ReadyToExportAdmin(admin.ModelAdmin):
    list_display = ['mftuser', 'created_by', 'created_at', 'is_downloaded', 'number_of_exports']


admin.site.register(CodingType, CodingTypeAdmin)
admin.site.register(BusinessCode, BusinessCodeAdmin)
admin.site.register(BankIdentifierCode, BankIdentifierCodeAdmin)
admin.site.register(IscDepartmentCode, IscDepartmentCodeAdmin)
admin.site.register(IscUserAccessCode, IscUserAccessCodeAdmin)
admin.site.register(DirectoryPermissionCode, DirectoryPermissionCodeAdmin)
admin.site.register(CustomerAccessCode, CustomerAccessCodeAdmin)
admin.site.register(CustomerAccessType, CustomerAccessTypeAdmin)
admin.site.register(DirectoryIndexCode, DirectoryIndexCodeAdmin)
admin.site.register(IscUser, IscUserAdmin)
admin.site.register(MftUser, MftUserAdmin)
admin.site.register(MftUserTemp, MftUserTempAdmin)
admin.site.register(Directory, DirectoryAdmin)
admin.site.register(Permission, PermissionAdmin)
# admin.site.register(CustomerAccess, CustomerAccessAdmin)
admin.site.register(CustomerBank, CustomerBankAdmin)
admin.site.register(OperationBusiness, OperationBusinessAdmin)
admin.site.register(ReadyToExport, ReadyToExportAdmin)
