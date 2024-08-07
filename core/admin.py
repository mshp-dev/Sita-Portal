from django.db import models
from django.contrib import admin
from django.conf import settings

from mftusers.utils import export_user_with_paths_v2, export_files_with_sftp
from .models import *


@admin.action(description="Set is_confirmed to True")
def confirm_selected_permissions(modeladmin, request, queryset):
    queryset.update(is_confirmed=True)


@admin.action(description="Set is_confirmed to False")
def unconfirm_selected_permissions(modeladmin, request, queryset):
    queryset.update(is_confirmed=False)


@admin.action(description="Reproduce export of users")
def make_ready_to_export_again(modeladmin, request, queryset):
    isc_user = IscUser.objects.get(user=request.user)
    for rte in queryset:
        export_user_with_paths_v2(rte.mftuser, isc_user)


@admin.action(description="Export selected users with sftp")
def export_selected_mftusers_with_sftp(modeladmin, request, queryset):
    for rte in queryset:
        rte.number_of_exports += 1
        rte.save()
        if rte.mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
            export_files_with_sftp(files_list=list[rte.webuser.path,], dest=settings.SFTP_DEFAULT_PATH)
        else:
            export_files_with_sftp(files_list=list[rte.webuser.path,], dest=settings.SFTP_EXTERNAL_USERS_PATH)


class CodingTypeAdmin(admin.ModelAdmin):
    list_display = ['type', 'description']


class BusinessCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'origin_address', 'foreign_address', 'remote_address']
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
    list_display = ['username', 'email', 'mobilephone', 'organization', 'created_by', 'get_owned_business', 'get_used_business']
    list_filter = ['is_confirmed', 'organization', 'owned_business', 'used_business', 'created_by']
    search_fields = ['username', 'firstname', 'lastname', 'email']
    ordering = ['username']


# class MftUserTempAdmin(admin.ModelAdmin):
#     list_display = ['username', 'email', 'mobilephone', 'organization', 'get_owned_business', 'created_by', 'is_confirmed']
#     list_filter = ['organization', 'business']
#     search_fields = ['username', 'firstname', 'lastname']
#     ordering = ['username']

class DirectoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'relative_path', 'bic', 'index_code', 'created_by']
    list_filter = ['index_code__code', 'bic', 'business']
    search_fields = ['relative_path', 'bic__description', 'business__description']
    ordering = ['name', 'relative_path']


class PermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'directory_path', 'permission', 'created_by', 'is_confirmed']
    list_filter = ['is_confirmed', 'permission', 'directory__index_code__code', 'directory__bic', 'directory__business']
    search_fields = ['user__username', 'directory__name', 'directory__relative_path']
    ordering = ['user__username', 'directory__relative_path']
    actions = [confirm_selected_permissions, unconfirm_selected_permissions]


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
    actions = [make_ready_to_export_again] #, export_selected_mftusers_with_sftp


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
# admin.site.register(MftUserTemp, MftUserTempAdmin)
admin.site.register(Directory, DirectoryAdmin)
admin.site.register(Permission, PermissionAdmin)
# admin.site.register(CustomerAccess, CustomerAccessAdmin)
admin.site.register(CustomerBank, CustomerBankAdmin)
admin.site.register(OperationBusiness, OperationBusinessAdmin)
admin.site.register(ReadyToExport, ReadyToExportAdmin)
