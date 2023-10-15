from django.utils import timezone
from django_cron import CronJobBase, Schedule
from django.conf import settings

from .models import Directory
from mftusers.utils import export_files_with_sftp

from datetime import timedelta, datetime as dt
import os, logging

logger = logging.getLogger(__name__)


class ExportCurrentConfirmedDirectoryTreeJob(CronJobBase):
    RUN_EVERY_MINS = 60 # every 1 hour
    RUN_AT_TIMES = ['22:00'] # on 22:00 every day

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    # schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'core.export_current_confirmed_directory_tree_job'

    def do(self):
        try:
            logger.info(f'daily job of export current confirmed directory tree started.')
            all_confirmed_dirs = Directory.objects.filter(is_confirmed=True).order_by('relative_path')
            all_buss_dirs = Directory.objects.filter(business__code__in=[buss['business'] for buss in all_confirmed_dirs.values('business').distinct()], parent=0).order_by('relative_path')
            external_confirmed_dirs = all_confirmed_dirs.filter(bic__sub_domain__code='amaliat.local').order_by('relative_path')
            external_buss_dirs = Directory.objects.filter(business__code__in=[buss['business'] for buss in external_confirmed_dirs.values('business').distinct()], parent=0).order_by('relative_path')
            portal_dirs_path = os.path.join(settings.MEDIA_ROOT, 'sita_portal_dirs.txt')
            with open(portal_dirs_path, mode='w') as portal_path_file:
                for abd in all_buss_dirs:
                    portal_path_file.write(f'{abd.absolute_path}\n')
                for acd in all_confirmed_dirs:
                    if acd.bic.sub_domain.code == 'nibn.ir':
                        portal_path_file.write(f'{acd.absolute_path}\n')
                    elif acd.bic.sub_domain.code == 'amaliat.local':
                        portal_path_file.write(f'{acd.remote_path}\n')
            export_files_with_sftp(files_list=[portal_dirs_path,], dest=settings.SFTP_PORTAL_DIRECTORIES_PATH, name='current_directories_in_portal.txt')
            logger.info(f'all confirmed directories path saved in media/sita_portal_dirs.txt by system and exported with sftp.')
            setad_dirs_path = os.path.join(settings.MEDIA_ROOT, 'setad_dirs.txt')
            with open(setad_dirs_path, mode='w') as txt_path_file:
                for ebd in external_buss_dirs:
                    txt_path_file.write(f'{ebd.foreign_path}\n')
                for ecd in external_confirmed_dirs:
                    txt_path_file.write(f'{ecd.foreign_path}\n')
            export_files_with_sftp(files_list=[setad_dirs_path,], dest=settings.SFTP_EXTERNAL_DIRECTORIES_PATH, name='current_directories_in_portal.txt')
            logger.info(f'external confirmed directories path saved in media/setad_dirs.txt by system and exported with sftp.')
        except Exception as e:
            logger.error(e)