from django.apps import AppConfig


class InvoiceConfig(AppConfig):
    name = 'invoice'

    # def ready(self):
    #     from .jobs import DeleteOldInvoicesJob
    #     invoices_job = DeleteOldInvoicesJob()
    #     invoices_job.start()
