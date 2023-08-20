from django.utils import timezone

from .models import Invoice

from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import timedelta, datetime as dt
import logging

logger = logging.getLogger(__name__)


class DeleteOldInvoicesJob():
    code = 'invoice.delete_old_invoices_cron'

    def start(self):
        scheduler = BackgroundScheduler(timezone=utc)
        scheduler.start()
        trigger = CronTrigger(
            year="*",
            month="*",
            day="*",
            hour="1",
            minute="0",
            second="0",
            timezone=utc
        )
        scheduler.add_job(
            self.job,
            trigger=trigger,
            max_instances=1,
            id=self.code
        )

    def job(self):
        try:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            logger.info(f'daily job of delete UNDEFINED invoices older than {thirty_days_ago} started.')
            old_invoices = Invoice.objects.filter(created_at__lte=thirty_days_ago, status=0) #confirm_or_reject='UNDEFINED'
            if old_invoices.count() > 1:
                logger.warn(f'found {old_invoices.count()} UNDEFINED invoices older than {thirty_days_ago}.')
                inv_ids = [oi.id for oi in old_invoices]
                # Invoice.objects.update()
                for oi in old_invoices:
                    oi.confirm_or_reject = 'REJECTED'
                    invoice.status = -1
                    oi.description = 'گذشتن مدت زمان 30/سی روز از ایجاد این درخواست'
                    oi.save()
                    logger.info(f'invoice with serial number {oi.serial_number} rejected by system.')
            else:
                logger.info(f'no UNDEFINED invoices older than {thirty_days_ago} found.')
        except Exception as e:
            logger.error(e)