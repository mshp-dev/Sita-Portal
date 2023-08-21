from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage

import os, zipfile


class OverwriteStorage(FileSystemStorage):
    
    def get_available_name(self, name, *args, **kwargs):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


class CodingType(models.Model):
    id               = models.AutoField(primary_key=True)
    type             = models.IntegerField(blank=False, unique=True)
    description      = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.description


class BaseCoding(models.Model):
    id               = models.AutoField(primary_key=True)
    type_id          = models.ForeignKey(CodingType, to_field='type', blank=False, on_delete=models.CASCADE)
    code             = models.CharField(max_length=255, blank=False)
    description      = models.TextField(max_length=500, blank=True, default="")

    class Meta:
        abstract = True

    def __str__(self):
        return self.description


class BusinessCode(BaseCoding):
    code             = models.CharField(max_length=20, blank=False, unique=True, default='...')
    origin_address   = models.CharField(max_length=100, blank=False, default='/DATA')
    foreign_address  = models.CharField(max_length=100, blank=False, default='/SMB')
    remote_address   = models.CharField(max_length=100, blank=False, default='resource:sftp://SETAD/SITA')


class OrganizationType(BaseCoding):
    code             = models.CharField(max_length=100, blank=False, unique=True, default='BANK')


class DomainName(BaseCoding):
    code             = models.CharField(max_length=250, blank=False, unique=True, default='example.com')


class BankIdentifierCode(BaseCoding):
    code              = models.CharField(max_length=20, blank=False, unique=True, default='_ISC')
    directory_name    = models.CharField(max_length=50, blank=False, default='_ISC')
    organization_type = models.ForeignKey(OrganizationType, to_field='code', blank=False, default='STATE_BANK', on_delete=models.CASCADE)
    sub_domain        = models.ForeignKey(DomainName, to_field='code', blank=True, default='nibn.ir', on_delete=models.CASCADE)


class IscUserAccessCode(BaseCoding):
    code             = models.CharField(max_length=20, blank=False, unique=True, default='CUSTOMER')


class IscDepartmentCode(BaseCoding):
    code             = models.CharField(max_length=100, blank=False, unique=True, default='ISC-OPR-OPR3-ISSO')
    access_type      = models.ForeignKey(IscUserAccessCode, to_field='code', blank=False, default='OPERATION',on_delete=models.CASCADE)


class DirectoryPermissionCode(BaseCoding):
    value            = models.IntegerField(blank=False, unique=True, default=256)
    code             = models.CharField(max_length=20, blank=False, unique=True, default='READ')


# class CustomerAccessCode(BaseCoding):
#     code             = models.CharField(max_length=10, blank=False, unique=True, default='MftUser')


class DirectoryIndexCode(BaseCoding):
    code             = models.CharField(max_length=10, blank=False, unique=True, default='0')


class IscUser(models.Model):
    user             = models.OneToOneField(User, on_delete=models.CASCADE)
    role             = models.ForeignKey(IscUserAccessCode, to_field='code', blank=False, on_delete=models.CASCADE)
    department       = models.ForeignKey(IscDepartmentCode, to_field='code', blank=False, on_delete=models.CASCADE)
    officephone      = models.DecimalField(max_digits=10, decimal_places=0, blank=False, default=12345678)
    mobilephone      = models.DecimalField(max_digits=12, decimal_places=0, blank=False, default=9123456789)

    def __str__(self):
        return f'{self.user.username} ({self.role})'

    def get_isc_user_owned_businesses(self):
        buss_str = 'سامانه/پروژه های'
        if self.role.code == 'ADMIN':
            opr_buss = BusinessCode.objects.all().order_by('description')
        else:
            opr_buss = BusinessCode.objects.filter(code__in=OperationBusiness.objects.filter(user=self, owned_by_user=True).values('access_on_bus__code')).order_by('description')
        
        if opr_buss.count() > 1:
            for bus in opr_buss:
                bus_str = str(bus)
                buss_str += f' {bus_str.replace("سامانه ", "")}،'
            return buss_str[:-1]
        else:
            return opr_buss.first()

    def get_isc_user_used_businesses(self):
        buss_str = 'سامانه/پروژه های'
        if self.role.code == 'ADMIN':
            opr_buss = BusinessCode.objects.all().order_by('description')
        else:
            opr_buss = BusinessCode.objects.filter(code__in=OperationBusiness.objects.filter(user=self, owned_by_user=False).values('access_on_bus__code')).order_by('description')
        
        if opr_buss.count() > 1:
            for bus in opr_buss:
                bus_str = str(bus)
                buss_str += f' {bus_str.replace("سامانه ", "")}،'
            return buss_str[:-1]
        else:
            return opr_buss.first()

    def get_iscuser_organizations(self):
        orgs_str = 'سازمان/بانک های'
        if self.role.code == 'ADMIN':
            cus_orgs = BankIdentifierCode.objects.all().order_by('description')
        else:
            cus_orgs = BankIdentifierCode.objects.filter(code__in=CustomerBank.objects.filter(user=self).values('access_on_bic__code')).order_by('description')
        if cus_orgs.count() > 1:
            for org in cus_orgs:
                org_str = str(org)
                orgs_str += f' {org_str.replace("بانک ", "").replace("شرکت ", "")}،'
            return orgs_str[:-1]
        else:
            return cus_orgs.first()


class MftUser(models.Model):
    id               = models.AutoField(primary_key=True)
    username         = models.CharField(max_length=101, blank=False)
    alias            = models.CharField(max_length=100, blank=True, default='')
    password         = models.CharField(max_length=255, blank=False, default='Isc@12345678')
    firstname        = models.CharField(max_length=50, blank=True)
    lastname         = models.CharField(max_length=50, blank=True)
    email            = models.EmailField(max_length=120, blank=False)
    officephone      = models.DecimalField(max_digits=8, decimal_places=0, blank=False, default=12345678)
    mobilephone      = models.DecimalField(max_digits=11, decimal_places=0, blank=False, default=9123456789)
    business         = models.ManyToManyField(BusinessCode) #, to_field='code', blank=False, default='NAHAB', on_delete=models.CASCADE)
    organization     = models.ForeignKey(BankIdentifierCode, to_field='code', blank=False, default='_ISC', on_delete=models.CASCADE)
    description      = models.TextField(max_length=1000, blank=True)
    # home_dir         = models.CharField(max_length=500, blank=True)
    ipaddr           = models.CharField(max_length=15, blank=True)
    # disk_quota       = models.IntegerField(blank=False, default=100)
    created_by       = models.ForeignKey(IscUser, blank=False, default=User.objects.get(id=1).id, on_delete=models.CASCADE)
    created_at       = models.DateTimeField(default=timezone.now)
    modified_at      = models.DateTimeField(default=timezone.now)
    is_confirmed     = models.BooleanField(blank=False, default=False)

    def get_owned_business(self):
        bus_list = [bus for bus in self.business.all()]
        buss = ""
        for b in bus_list:
            buss += f'{b.code},'
        return buss[:-1]

    def get_used_business(self, obj=False):
        bus_list = BusinessCode.objects.all().exclude(code__in=self.business.all().values('code')).values('code')
        bus_dirs = Directory.objects.filter(parent=0, business__code__in=bus_list)
        if obj:
            return Permission.objects.filter(user=self.id, directory__parent=0, directory__business__code__in=bus_list).values('directory__business__description')
        else:
            buss = ""
            for bus_dir in bus_dirs:
                if Permission.objects.filter(user=self.id, directory=bus_dir.id).exists():
                    buss += f'{bus_dir.business.code},'
            return buss[:-1]

    def __str__(self):
        return f'{self.username} ({self.organization})'


class MftUserTemp(models.Model):
    id               = models.AutoField(primary_key=True)
    username         = models.CharField(max_length=101, blank=False)
    alias            = models.CharField(max_length=100, blank=True, default='')
    password         = models.CharField(max_length=255, blank=False, default='Isc@12345678')
    firstname        = models.CharField(max_length=50, blank=True)
    lastname         = models.CharField(max_length=50, blank=True)
    email            = models.EmailField(max_length=120, blank=False)
    officephone      = models.DecimalField(max_digits=8, decimal_places=0, blank=False, default=12345678)
    mobilephone      = models.DecimalField(max_digits=11, decimal_places=0, blank=False, default=9123456789)
    business         = models.ManyToManyField(BusinessCode) #, to_field='code', blank=False, default='NAHAB', on_delete=models.CASCADE)
    organization     = models.ForeignKey(BankIdentifierCode, to_field='code', blank=False, default='_ISC', on_delete=models.CASCADE)
    description      = models.TextField(max_length=1000, blank=True)
    # home_dir         = models.CharField(max_length=500, blank=True)
    ipaddr           = models.CharField(max_length=15, blank=True)
    # disk_quota       = models.IntegerField(blank=False, default=100)
    created_by       = models.ForeignKey(IscUser, blank=False, default=User.objects.get(id=1).id, on_delete=models.CASCADE)
    created_at       = models.DateTimeField(default=timezone.now)
    modified_at      = models.DateTimeField(default=timezone.now)
    is_confirmed     = models.BooleanField(blank=False, default=False)

    def get_owned_business(self):
        bus_list = [bus for bus in self.business.all()]
        buss = ""
        for b in bus_list:
            buss += f'{b.code},'
        return buss[:-1]

    def get_used_business(self, obj=False):
        bus_list = BusinessCode.objects.all().exclude(code__in=self.business.all().values('code')).values('code')
        bus_dirs = Directory.objects.filter(parent=0, business__code__in=bus_list)
        if obj:
            return Permission.objects.filter(user=self.id, directory__parent=0, directory__business__code__in=bus_list).values('directory__business__description')
        else:
            buss = ""
            for bus_dir in bus_dirs:
                if Permission.objects.filter(user=self.id, directory=bus_dir.id).exists():
                    buss += f'{bus_dir.business.code},'
            return buss[:-1]

    def __str__(self):
        return f'{self.username} ({self.organization})'


class Directory(models.Model):
    id               = models.AutoField(primary_key=True)
    name             = models.CharField(max_length=255, blank=False)
    parent           = models.IntegerField(blank=False, default=0)
    children         = models.CharField(max_length=500, blank=True)
    relative_path    = models.CharField(max_length=500, blank=False)
    business         = models.ForeignKey(BusinessCode, to_field='code', blank=False, default='NAHAB', on_delete=models.CASCADE)
    bic              = models.ForeignKey(BankIdentifierCode, to_field='code', blank=False, on_delete=models.CASCADE)
    created_by       = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at       = models.DateTimeField(default=timezone.now)
    index_code       = models.ForeignKey(DirectoryIndexCode, to_field='code', default='0', blank=False, on_delete=models.CASCADE)
    is_confirmed     = models.BooleanField(blank=False, default=False)

    def __str__(self):
        return f'{self.name} ({self.relative_path.replace(f"/{self.name}", "")})'
    
    @property
    def absolute_path(self):
        return f'{self.business.origin_address}/{self.relative_path}'
    
    @property
    def foreign_path(self):
        return f'{self.business.foreign_address}/{self.relative_path}'
    
    @property
    def remote_path(self):
        return f'{self.business.remote_address}/{self.relative_path}'


class Permission(models.Model):
    id               = models.AutoField(primary_key=True)
    user             = models.ForeignKey(MftUser, blank=False, on_delete=models.CASCADE)
    directory        = models.ForeignKey(Directory, blank=False, on_delete=models.CASCADE)
    permission       = models.IntegerField(blank=False, default=256)
    # permission       = models.ForeignKey(DirectoryPermissionCode, to_field='value', blank=False, null=True, on_delete=models.CASCADE)
    created_by       = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at       = models.DateTimeField(default=timezone.now)
    is_confirmed     = models.BooleanField(blank=False, default=False)

    def __str__(self):
        # user = MftUser.objects.get(id=self.user_id)
        perm = DirectoryPermissionCode.objects.get(value=self.permission)
        return f'{self.user} has {perm.code} access on {self.directory.absolute_path}'

    @property
    def directory_path(self):
        if self.directory.bic.sub_domain.code == 'nibn.ir' and self.user.organization.sub_domain.code == 'nibn.ir':
            return self.directory.absolute_path
        elif self.directory.bic.sub_domain.code != 'nibn.ir' and self.user.organization.sub_domain.code == 'nibn.ir':
            return self.directory.remote_path
        elif self.directory.bic.sub_domain.code != 'nibn.ir' and self.user.organization.sub_domain.code != 'nibn.ir':
            return self.directory.foreign_path


# class CustomerAccess(models.Model):
#     id               = models.AutoField(primary_key=True)
#     user             = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
#     access_on        = models.ForeignKey(CustomerAccessCode, to_field='code', blank=False, on_delete=models.CASCADE)
#     access_type      = models.ForeignKey(CustomerAccessType, to_field='code', blank=False, on_delete=models.CASCADE)
#     target_id        = models.IntegerField(blank=False, default=-1)
#     created_at       = models.DateTimeField(default=timezone.now)

#     def __str__(self):
#         return f'{self.user.user.username} has {self.access_type} access on {self.access_on} with id {self.target_id}'


class CustomerBank(models.Model):
    id               = models.AutoField(primary_key=True)
    user             = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    access_on_bic    = models.ForeignKey(BankIdentifierCode, to_field='code', blank=False, on_delete=models.CASCADE)
    
    def __str__(self):
        return f'{self.user.user.username} access on {self.access_on_bic}'


class OperationBusiness(models.Model):
    id               = models.AutoField(primary_key=True)
    user             = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    access_on_bus    = models.ForeignKey(BusinessCode, to_field='code', blank=False, default='NAHHB', on_delete=models.CASCADE)
    owned_by_user    = models.BooleanField(blank=False, default=True)
    
    def __str__(self):
        return f'{self.user.user.username} access on {self.access_on_bus}'
    
    @property
    def user_department(self):
        return f'{self.user.department}'


class ReadyToExport(models.Model):
    id                  = models.AutoField(primary_key=True)
    mftuser             = models.OneToOneField(MftUser, blank=False, on_delete=models.CASCADE)
    webuser             = models.FileField(upload_to='exports/', storage=OverwriteStorage(), default='template.xml')
    paths               = models.FileField(upload_to='exports/', storage=OverwriteStorage(), default='paths.csv')
    # is_downloaded       = models.BooleanField(blank=False, default=False)
    number_of_exports   = models.IntegerField(blank=False, default=1)
    number_of_downloads = models.IntegerField(blank=False, default=0)
    created_by          = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at          = models.DateTimeField(default=timezone.now)

    def generate_zip_file(self, name='export'):
        path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(self.webuser.path, arcname=self.webuser.name.split('/')[-1])
            # zf.write(self.paths.path, arcname=self.paths.name.split('/')[-1])
        return os.path.join(os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.zip'))