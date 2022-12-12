from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User

from core.models import BaseCoding, IscUser, MftUser, Directory, BusinessCode

from datetime import datetime as dt
import random


class InvoiceType(BaseCoding):
    code          = models.CharField(max_length=20, blank=False, unique=True, default='DEFAULT')
    serial_prefix = models.CharField(max_length=20, blank=False, default='SITA')


class BaseInvoice(models.Model):
    id                = models.AutoField(primary_key=True)
    invoice_type      = models.ForeignKey(InvoiceType, to_field='code', null=True, on_delete=models.CASCADE)
    serial_number     = models.CharField(max_length=50, blank=False, default=None)
    confirm_or_reject = models.CharField(max_length=10, blank=False, default='UNDEFINED')
    created_by        = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at        = models.DateTimeField(default=timezone.now)
        
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        if self.serial_number is None:
            self.serial_number = self.generate_serial_number()
        super(BaseInvoice, self).save(*args, **kwargs)

    def generate_serial_number(self):
        itype = str(self.invoice_type.id)
        return f'{itype}{dt.now().strftime("%y%m%d%H%M%S")}'


class Invoice(BaseInvoice):
    mftuser       = models.IntegerField(blank=False)
    used_business = models.IntegerField(default=0, blank=True)
    
    def get_mftuser(self):
        return MftUser.objects.get(pk=self.mftuser)

    def generate_serial_number(self):
        serial_number = super(Invoice, self).generate_serial_number()
        uid = str(self.mftuser)
        count = len(uid)
        zero = 10 - count
        divided = int(zero / 2)
        remained = zero % 2
        invoice_type = InvoiceType.objects.get(pk=int(serial_number[0]))
        return f'{invoice_type.serial_prefix}{"0" * divided}{uid}{"0" * divided}{"0" * remained if remained > 0 else ""}{serial_number}'

    def get_used_business(self):
        if self.used_business != 0:
            return None
        else:
            return BusinessCode.objects.get(pk=self.used_business)


class PreInvoice(BaseInvoice):
    directories_list  = models.CharField(max_length=1000, default='', blank=False)

    def generate_serial_number(self):
        serial_number = super(PreInvoice, self).generate_serial_number()
        invoice_type = InvoiceType.objects.get(pk=int(serial_number[0]))
        return f'{invoice_type.serial_prefix}0000000000{serial_number}'
    
    def get_all_directories(self):
        dir_ids = [int(d) for d in self.directories_list.split(',')[:-1]]
        all_dirs = Directory.objects.filter(pk__in=dir_ids)
        return all_dirs