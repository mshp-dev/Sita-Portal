from django.utils import timezone
from django_cron import CronJobBase, Schedule

from .models import Invoice

from datetime import timedelta, datetime as dt
import logging

logger = logging.getLogger(__name__)


class DeleteOldInvoicesJob(CronJobBase):
    RUN_EVERY_MINS = 1440 # every 24 hours
    RUN_AT_TIMES = ['23:00'] # on 23:00 every day

    # schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'invoice.delete_old_invoice_job'

    # def start(self):
        # scheduler = BackgroundScheduler(timezone=utc)
        # scheduler.start()
        # trigger = CronTrigger(
        #     year="*",
        #     month="*",
        #     day="*",
        #     hour="23",
        #     minute="30",
        #     second="0",
        #     timezone=utc
        # )
        # scheduler.add_job(
        #     self.job,
        #     trigger=trigger,
        #     max_instances=1,
        #     id=self.code
        # )

    def do(self):
        try:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            logger.info(f'daily job of delete UNDEFINED invoices older than {thirty_days_ago} started.')
            old_invoices = Invoice.objects.filter(created_at__lte=thirty_days_ago, status=0) #confirm_or_reject='UNDEFINED'
            if old_invoices.count() > 1:
                logger.warn(f'found {old_invoices.count()} UNDEFINED invoices older than {thirty_days_ago}.')
                # inv_ids = [oi.id for oi in old_invoices]
                # Invoice.objects.update()
                for oi in old_invoices:
                    oi.confirm_or_reject = 'REJECTED'
                    oi.status = -1
                    oi.description = 'گذشتن مدت زمان 30/سی روز از ایجاد این درخواست'
                    oi.save()
                    logger.info(f'invoice with serial number {oi.serial_number} rejected by system.')
            else:
                logger.info(f'no UNDEFINED invoices older than {thirty_days_ago} found.')
        except Exception as e:
            logger.error(e)