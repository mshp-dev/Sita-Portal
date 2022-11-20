from django.db import models
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import User

from core.models import IscUser, MftUser, Directory, Permission, BankIdentifierCode

from datetime import datetime as dt
import random

class Invoice(models.Model):
    id         = models.AutoField(primary_key=True)
    mftuser    = models.IntegerField(blank=False)
    created_by = models.ForeignKey(IscUser, blank=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    
    @property
    def serial_number(self):
        uid = str(self.mftuser)
        count = len(uid)
        zero = 5 - count
        start = f'1{"0" * (zero - 1)}'
        end = f'9{"9" * (zero - 1)}'
        rand = random.randint(int(start), int(end))
        return f'SITAUSER{count}{rand}{uid}{dt.now().strftime("%y%m%d%H%M")}'