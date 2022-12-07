from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User

from core.models import BaseCoding, IscUser, MftUser, Directory

from datetime import datetime as dt
import random


class InvoiceType(BaseCoding):
    code = models.CharField(max_length=20, blank=False, unique=True, default='DEFAULT')


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

    def generate_serial_number(self, prefix=''):
        uid = str(self.mftuser)
        count = len(uid)
        zero = 5 - count
        start = f'1{"0" * (zero - 1)}'
        end = f'9{"9" * (zero - 1)}'
        rand = random.randint(int(start), int(end))
        return f'{prefix}{count}{rand}{uid}{dt.now().strftime("%y%m%d%H%M")}'


class Invoice(BaseInvoice):
    mftuser       = models.IntegerField(blank=False)
    used_business = models.IntegerField(default=0, blank=True)
    
    def get_mftuser(self):
        return MftUser.objects.get(pk=self.mftuser)

    def generate_serial_number(self, prefix='SITAUSER'):
        return super(Invoice, self).generate_serial_number(prefix)


class PreInvoice(BaseInvoice):
    directories_list  = models.CharField(max_length=1000, default='', blank=False)

    def generate_serial_number(self, prefix='SITADIR'):
        return super(PreInvoice, self).generate_serial_number(prefix)
    
    def get_all_directories(self):
        dir_ids = [int(d) for d in self.directories_list.split(',')[:-1]]
        all_dirs = Directory.objects.filter(pk__in=dir_ids)
        return all_dirs