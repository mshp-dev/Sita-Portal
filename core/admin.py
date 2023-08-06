from django.db import models
from django.contrib import admin
from .models import *


class CodingTypeAdmin(admin.ModelAdmin):
    list_display = ['type', 'description']


class BusinessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'origin_address', 'remote_address']
    list_filter = ['origin_address', 'remote_address']
    ordering = ['description']


class BankIdentifierCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'organization_type', 'description', 'type_id', 'sub_domain']
    ordering = ['description']


class IscUserAccessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class IscDepartmentCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id', 'access_type']


class DirectoryPermissionCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'value', 'type_id']
    ordering = ['value']


class DomainNameAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class OrganizationTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class DirectoryIndexCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'type_id']


class IscUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department']
    list_filter = ['role', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering = ['user__username']


class MftUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'mobilephone', 'organization', 'get_used_business', 'get_owned_business', 'created_by', 'is_confirmed']
    list_filter = ['organization', 'business']
    search_fields = ('username', 'firstname', 'lastname')
    ordering = ['username']


class MftUserTempAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'mobilephone', 'organization', 'get_used_business', 'get_owned_business', 'created_by', 'is_confirmed']
    list_filter = ['organization', 'business']
    search_fields = ('username', 'firstname', 'lastname')
    ordering = ['username']

class DirectoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'relative_path', 'bic', 'index_code', 'created_by']
    list_filter = ['index_code__code', 'bic', 'business']
    search_fields = ['relative_path', 'bic__description', 'business__description']
    ordering = ['name', 'relative_path']


class PermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'directory_path', 'permission', 'created_by', 'is_confirmed']
    list_filter = ['permission', 'directory__bic', 'directory__business', 'created_by', 'is_confirmed']
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
    list_display = ['mftuser', 'created_by', 'created_at', 'number_of_exports', 'number_of_downloads']
    search_fields = ['mftuser__username']


admin.site.register(CodingType, CodingTypeAdmin)
admin.site.register(BusinessCode, BusinessCodeAdmin)
admin.site.register(BankIdentifierCode, BankIdentifierCodeAdmin)
admin.site.register(IscDepartmentCode, IscDepartmentCodeAdmin)
admin.site.register(IscUserAccessCode, IscUserAccessCodeAdmin)
admin.site.register(DirectoryPermissionCode, DirectoryPermissionCodeAdmin)
admin.site.register(DomainName, DomainNameAdmin)
admin.site.register(OrganizationType, OrganizationTypeAdmin)
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
