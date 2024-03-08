from django.db import models
from django.utils import timezone
from django.conf import settings

from core.models import BusinessCode, OverwriteStorage, IscUser, DirectoryIndexCode, DirectoryPermissionCode
from invoice.models import BaseInvoice, InvoiceType

import random


class SetadUserInvoice(BaseInvoice):
    username    = models.CharField(max_length=100, blank=False)
    firstname   = models.CharField(max_length=100, blank=False)
    lastname    = models.CharField(max_length=100, blank=False)
    email       = models.CharField(max_length=100, blank=False)
    officephone = models.CharField(max_length=100, blank=False)
    mobilephone = models.CharField(max_length=100, blank=False)
    department  = models.CharField(max_length=100, blank=False)
    business    = models.CharField(max_length=10000, blank=False, default='')

    def __str__(self):
        return self.username

    def generate_serial_number(self):
        serial_number = super(SetadUserInvoice, self).generate_serial_number()
        invoice_type = InvoiceType.objects.get(pk=int(serial_number[0]))
        return f'{invoice_type.serial_prefix}000{random.randint(1000,9999)}000{serial_number}'

    def set_business(self, buss):
        self.business = ','.join(BusinessCode.objects.get(pk=int(bus)).code.replace('SETAD_', '') for bus in buss)


class AzmoonDirectory(models.Model):
    name          = models.CharField(max_length=255, blank=False)
    parent        = models.IntegerField(blank=False, default=0)
    children      = models.CharField(max_length=500, blank=True)
    absolute_path = models.CharField(max_length=1000, blank=False)
    business      = models.ForeignKey(BusinessCode, to_field='code', blank=False, default='NAHAB', on_delete=models.CASCADE)
    created_by    = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at    = models.DateTimeField(default=timezone.now)
    index_code    = models.ForeignKey(DirectoryIndexCode, to_field='code', default='0', blank=False, on_delete=models.CASCADE)

    def __str__(self):
        return self.absolute_path


class AzmoonDirectoryPermission(models.Model):
    invoice      = models.OneToOneField(SetadUserInvoice, blank=False, on_delete=models.CASCADE)
    directory    = models.ForeignKey(AzmoonDirectory, blank=False, on_delete=models.CASCADE)
    permission   = models.IntegerField(blank=False, default=256)
    created_by   = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at   = models.DateTimeField(default=timezone.now)
    is_confirmed = models.BooleanField(blank=False, default=False)

    def __str__(self):
        perm = DirectoryPermissionCode.objects.get(value=self.permission)
        return f'{self.invoice.username} has {perm.code} access on {self.directory.absolute_path}'


class ReadyToExportSetad(models.Model):
    invoice             = models.OneToOneField(SetadUserInvoice, blank=False, on_delete=models.CASCADE)
    webuser             = models.FileField(upload_to='exports/setad/', storage=OverwriteStorage(), default='template.xml')
    paths               = models.FileField(upload_to='exports/setad/', storage=OverwriteStorage(), default='paths.csv')
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