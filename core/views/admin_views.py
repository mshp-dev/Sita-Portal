from multiprocessing import context
from django import template
from django.db.models import Q
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, JsonResponse, FileResponse
from django.template import loader
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.hashers import make_password
from django.conf import settings

from invoice.models import Invoice, PreInvoice
from mftusers.utils import *
from core.models import *
from core.forms import *

from datetime import datetime as dt

import logging, os

logger = logging.getLogger(__name__)


@login_required(login_url="/login/")
def add_data_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    username = str(isc_user.user.username)
    access = str(isc_user.role.code)
    bus_msg = org_msg = ''
    submit_error = False

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    organization_form = AddOrganizationForm()
    business_form = AddBusinessForm()
    organization_form.fields['organization_type'].choices = [(org_type.id, org_type) for org_type in OrganizationType.objects.all().order_by('description')]
    organization_form.fields['sub_domain'].choices = [(dn.id, dn) for dn in DomainName.objects.all().order_by('description')]
    
    if request.method == 'POST':
        if request.POST.get("form-type") == "organization-form":
            organization_form = AddOrganizationForm(request.POST)
            organization_form.fields['organization_type'].choices = [(org_type.id, org_type) for org_type in OrganizationType.objects.all().order_by('description')]
            organization_form.fields['sub_domain'].choices = [(dn.id, dn) for dn in DomainName.objects.all().order_by('description')]
            if organization_form.is_valid():
                bic = BankIdentifierCode(
                    type_id=CodingType.objects.get(type=1001),
                    code=organization_form.cleaned_data.get("organization_code"),
                    description=organization_form.cleaned_data.get("organization_description"),
                    directory_name=organization_form.cleaned_data.get("directory_name"),
                    organization_type=organization_form.cleaned_data.get("organization_type"),
                    sub_domain=organization_form.cleaned_data.get("sub_domain")
                )
                bic.save()
                logger.info(f'{isc_user.user.username} added {bic.code} organization.', request)
                for bus in BusinessCode.objects.all().exclude(code__startswith='SETAD_', code=F('description')):
                    try:
                        bus_dir = Directory.objects.get(business=bus, parent=0)
                    except Exception as e:
                        logger.error(e, request)
                        continue
                    ch_dir = Directory(
                        name=bic.directory_name,
                        relative_path=f'{bus.code}/{bic.directory_name}',
                        index_code=DirectoryIndexCode.objects.get(code=-1),
                        parent=bus_dir.id,
                        business=bus,
                        bic=bic,
                        created_by=isc_user
                    )
                    ch_dir.save()
                    logger.info(f'a directory in {ch_dir.absolute_path} created.', request)
                    bus_dir.children += f'{ch_dir.id},'
                    bus_dir.save()
                org_msg = f'سازمان/بانک {bic.code} با موفقیت اضافه گردید.'
                submit_error = False
            else:
                org_msg = business_form.errors
                submit_error = True
        elif request.POST.get("form-type") == "business-form":
            business_form = AddBusinessForm(request.POST)
            if business_form.is_valid():
                bus = BusinessCode(
                    type_id=CodingType.objects.get(type=1009),
                    code=business_form.cleaned_data.get("code"),
                    description=business_form.cleaned_data.get("description"),
                    origin_address=business_form.cleaned_data.get("origin_address"),
                    foreign_address=business_form.cleaned_data.get("foreign_address"),
                    remote_address=business_form.cleaned_data.get("remote_address")
                )
                bus.save()
                dir_ = Directory(
                    name=bus.code,
                    relative_path=bus.code,
                    index_code=DirectoryIndexCode.objects.get(code=0),
                    parent=0,
                    business=bus,
                    bic=BankIdentifierCode.objects.get(code='BMJI'),
                    created_by=isc_user
                )
                dir_.save()
                logger.info(f'{isc_user.user.username} added {bus.code} business.', request)
                for bic in BankIdentifierCode.objects.all():
                    ch_dir = Directory(
                        name=bic.directory_name,
                        relative_path=f'{bus.code}/{bic.directory_name}',
                        index_code=DirectoryIndexCode.objects.get(code=-1),
                        parent=dir_.id,
                        business=bus,
                        bic=bic,
                        created_by=isc_user
                    )
                    ch_dir.save()
                    logger.info(f'a directory in {ch_dir.absolute_path} created.', request)
                    dir_.children += f'{ch_dir.id},'
                dir_.save()
                bus_msg = f'پروژه/سامانه {bus.code} با موفقیت اضافه گردید.'
                submit_error = False
            else:
                bus_msg = business_form.errors
                submit_error = True
    context = {
        "username": username,
        "access": access,
        "organization_form": organization_form,
        "business_form": business_form,
        'bus_msg': bus_msg,
        'org_msg': org_msg,
        "error": submit_error
    }
    return render(request, "core/add-data.html", context)


@login_required(login_url="/login/")
def generate_report_view(request, *args, **kwargs):
    isc_user          = IscUser.objects.get(user=request.user)
    username          = str(isc_user.user.username)
    access            = str(isc_user.role.code)
    report_items      = []
    directory_indexes = []
    index_code        = request.GET.get('dd', '-2')
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')
    
    all_buss = BusinessCode.objects.all().exclude(code__startswith='SETAD_', code=F('description')).order_by('description')
    for bus in all_buss:
        report_items.append(
            {
                'bus_code': bus.code,
                'bus_description': bus.description,
                'dir_count': Directory.objects.filter(
                    business=bus,
                    index_code=DirectoryIndexCode.objects.get(code=index_code)
                ).count(),
                'user_count': MftUser.objects.filter(business=bus).count()
            }
        )
    # for di in DirectoryIndexCode.objects.all().order_by('id')

    context = {
        "username": username,
        "access": access,
        "report_items": report_items,
        "directory_indexes" : DirectoryIndexCode.objects.all().order_by('id')
    }
    return render(request, "core/report.html", context)


@login_required(login_url="/login/")
def manage_data_view(request, *args, **kwargs):
    isc_user        = IscUser.objects.get(user=request.user)
    username        = str(isc_user.user.username)
    access          = str(isc_user.role.code)
    # mftusers        = MftUser.objects.filter(is_confirmed=False).order_by('username')
    # deleted_users   = MftUserTemp.objects.filter(description__icontains=f"%deleted%").order_by('username')
    # invoices        = Invoice.objects.filter(processed=False).order_by('created_at')
    invoices        = Invoice.objects.all().order_by('-created_at')
    pre_invoices    = PreInvoice.objects.all().order_by('-created_at')
    # elements        = []
    # new_users       = []
    # changed_users   = []
    # differences     = {}

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'GET':
            query = request.GET.get('q')
            filtered_invs = {
                'invoices': [inv.id for inv in invoices],
                'pre_invoices': [inv.id for inv in pre_invoices]
            }
            if query != '':
                filtered_invs = {
                    'invoices': [],
                    'pre_invoices': []
                }
                if ',' in query:
                    for inv in query.split(','):
                        filtered_invs['invoices'].append(int(inv))
                        filtered_invs['pre_invoices'].append(int(inv))
                else:
                    for inv in invoices:
                        # mftuser = inv.get_mftuser()
                        buss = [bus.description for bus in inv.mftuser.owned_business.all()]
                        if query in inv.mftuser.username or query in inv.mftuser.alias or query in inv.mftuser.organization.description or query in inv.serial_number or query in inv.created_by.user.username or query in inv.get_jalali_created_at() or query in buss:
                            filtered_invs['invoices'].append(inv.id)
                    for inv in pre_invoices:
                        if query in inv.serial_number or query in inv.created_by.user.username or query in inv.get_jalali_created_at():
                            filtered_invs['pre_invoices'].append(inv.id)
            return JsonResponse(data={"filtered_invs": filtered_invs}, safe=False)

    # for user in mftusers:
        #     if MftUserTemp.objects.filter(username=user.username).exists():
        #         changed_users.append(user)
        #         differences[user.username] = get_user_differences(
        #             MftUserTemp.objects.filter(username=user.username).first(),
        #             user
        #         )
        #     else:
        #         new_users.append(user)
    
    context = {
        'username': username,
        'admin_view': True,
        'access': access,
        'invoices': invoices,
        'pre_invoices': pre_invoices,
        # 'undefined_invoices': Invoice.objects.filter(status=0).order_by('-created_at'),
        # 'undefined_pre_invoices': PreInvoice.objects.filter(status=0).order_by('-created_at'),
        # 'confirmed_invoices': Invoice.objects.filter(status=1).order_by('-created_at'),
        # 'confirmed_pre_invoices': PreInvoice.objects.filter(status=1).order_by('-created_at'),
        # 'rejected_invoices': Invoice.objects.filter(status=-1).order_by('-created_at'),
        # 'rejected_pre_invoices': PreInvoice.objects.filter(status=-1).order_by('-created_at'),
        # 'elements': get_users_with_changed_permissions(),
        # 'users': mftusers,
        # 'new_users': new_users,
        # 'deleted': deleted_users,
        # 'changed_users': changed_users,
        # 'differences': differences,
        'selected_tab': request.GET.get('tab', '')
    }

    return render(request, "core/manage-data.html", context)


@login_required(login_url="/login/")
def export_data_view(request, *args, **kwargs):
    isc_user          = IscUser.objects.get(user=request.user)
    username          = str(isc_user.user.username)
    access            = str(isc_user.role.code)
    exported_mftusers = ReadyToExport.objects.all().order_by('-mftuser__modified_at') #-created_at
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    context = {
        'username': username,
        'admin_view': True,
        'access': access,
        'exported': exported_mftusers,
    }

    if request.is_ajax():
        if request.method == 'POST':
            exported_user = ReadyToExport.objects.get(pk=int(request.POST.get('eid')))
            # os.remove(exported_user.export.path)
            # exported_user.is_downloaded = True
            exported_user.number_of_downloads += 1
            exported_user.save()
            logger.info(f'mftuser {exported_user.mftuser.username} exported successfully.', request)
            logger.info(f'export current confirmed directory tree started.', request)
            export_current_confirmed_directory_tree()
            response = {'result': 'success', 'deleted': exported_user.mftuser.username.replace('.', '')}
            return JsonResponse(data=response, safe=False)
        elif request.method == 'GET':
            query = request.GET.get('q')
            filtered_mftusers = list(user.id for user in context['exported'])
            if query != '':
                filtered_mftusers = list(user.id for user in context['exported'] if query in user.mftuser.username or query in user.mftuser.alias or query in user.mftuser.organization.description)
            return JsonResponse(data={"filtered_mftusers": filtered_mftusers}, safe=False)
            # context['exported'] = filtered_mftusers
            # html = render_to_string(
            #     template_name="includes/users-list.html", context=context
            # )
            # data_dict = {"html_from_view": html}
            # return JsonResponse(data=data_dict, safe=False)

    return render(request, "core/export-data.html", context)


@login_required(login_url="/login/")
def bulk_confirm_export_view(request, *args, **kwargs):
    isc_user          = IscUser.objects.get(user=request.user)
    username          = str(isc_user.user.username)
    access            = str(isc_user.role.code)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')
    
    if request.is_ajax():
        if request.method == 'POST':
            response = {}
            users_list = []
            try:
                users_list = [str(user.replace('\n', '')) for user in request.POST.get('users_list').split(',')]
                for user in users_list:
                    undf_invs = Invoice.objects.filter(mftuser__username=user, confirm_or_reject='UNDEFINED')
                    # Permission.objects.
                if len(files_list) > 1:
                    export_files_with_sftp(files_list=files_list, dest=settings.SFTP_DEFAULT_PATH)
                    logger.info(f'all mftusers exported with sftp by {isc_user.user.username} successfully.', request)
                else:
                    mftuser = MftUser.objects.get(pk=rtes.first().mftuser.id)
                    if mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_DEFAULT_PATH)
                    else:
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_EXTERNAL_USERS_PATH)
                    logger.info(f'mftuser with id {rtes.first().mftuser.id} exported with sftp by {isc_user.user.username} successfully.', request)
                logger.info(f'export current confirmed directory tree started.', request)
                export_current_confirmed_directory_tree()
                response = {
                    'result': 'success',
                    'message': 'تأیید و استخراج کاربران با موفقیت انجام شد.'
                }
            except Exception as e:
                logger.error(e, request)
                response = {
                    'result': 'error',
                    'message': 'خطایی رخ داده است، با مدیر سیستم تماس بگیرید!'
                }
            finally:
                return JsonResponse(data=response, safe=False)

    context = {
        'username': username,
        'admin_view': True,
        'access': access,
    }

    return render(request, "core/bulk-confirm-export.html", context)


@login_required(login_url="/login/")
def sftp_user_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    rtes     = ReadyToExport.objects.all() if id == 0 else ReadyToExport.objects.filter(pk=id)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            response = {}
            files_list = []
            try:
                files_list = [re.webuser.path for re in rtes]
                if len(files_list) > 1:
                    export_files_with_sftp(files_list=files_list, dest=settings.SFTP_DEFAULT_PATH)
                    logger.info(f'all mftusers exported with sftp by {isc_user.user.username} successfully.', request)
                else:
                    mftuser = MftUser.objects.get(pk=rtes.first().mftuser.id)
                    if mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_DEFAULT_PATH)
                    else:
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_EXTERNAL_USERS_PATH)
                    logger.info(f'mftuser with id {rtes.first().mftuser.id} exported with sftp by {isc_user.user.username} successfully.', request)
                response = {'result': 'success'}
            except Exception as e:
                logger.error(e, request)
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def bulk_sftp_user_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            response = {}
            try:
                users_list = [str(user.replace('\n', '')) for user in request.POST.get('users_list').split(',')]
                rtes = ReadyToExport.objects.filter(mftuser__username__in=users_list)
                for rte in rtes:
                    files_list = [rte.webuser.path,]
                    mftuser = MftUser.objects.get(pk=rte.mftuser.id)
                    if mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_DEFAULT_PATH)
                    else:
                        export_files_with_sftp(files_list=files_list, dest=settings.SFTP_EXTERNAL_USERS_PATH)
                    logger.info(f'mftuser with id {rte.mftuser.id} exported with sftp by {isc_user.user.username} successfully.', request)
                    rte.number_of_downloads += 1
                    rte.save()
                    logger.info(f'mftuser {rte.mftuser.username} exported successfully.', request)
                # nibn_users_files_list = []
                # non_nibn_users_files_list = []
                # for rte in rtes:
                #     # files_list = [rte.webuser.path,]
                #     mftuser = MftUser.objects.get(pk=rte.mftuser.id)
                #     if mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
                #         nibn_users_files_list.append(rte.webuser.path)
                #     else:
                #         non_nibn_users_files_list.append(rte.webuser.path)
                #     logger.info(f'mftuser with id {rte.mftuser.id} exported with sftp by {isc_user.user.username} successfully.')
                #     rte.number_of_downloads += 1
                #     rte.save()
                #     logger.info(f'mftuser {rte.mftuser.username} exported successfully.')
                # export_files_with_sftp(files_list=nibn_users_files_list, dest=settings.SFTP_DEFAULT_PATH)
                # export_files_with_sftp(files_list=non_nibn_users_files_list, dest=settings.SFTP_EXTERNAL_USERS_PATH)
                logger.info(f'export current confirmed directory tree started.', request)
                export_current_confirmed_directory_tree()
                response = {
                    'result': 'success',
                    'users': users_list,
                    'message': 'استخراج کاربران با موفقیت انجام شد.'
                }
            except Exception as e:
                logger.error(e, request)
                response = {
                    'result': 'error',
                    'message': 'خطایی رخ داده است، با مدیر سیستم تماس بگیرید!'
                }
            finally:
                return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def download_mftuser_view(request, id, *args, **kwargs):
    isc_user     = IscUser.objects.get(user=request.user)
    downloadable = None if id == 0 else ReadyToExport.objects.get(pk=id)
    response     = None
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if downloadable:
        # mime_type, _ = mimetypes.guess_type(downloadable.export.path)
        response = FileResponse(open(downloadable.generate_zip_file(name=downloadable.mftuser.username), 'rb'), as_attachment=True)#, content_type=mime_type)
        response['Content-Disposition'] = f"attachment; filename={downloadable.mftuser.username}.zip"
        response['Content-Type'] = "file/zip"
        logger.info(f'{downloadable.mftuser.username}.zip downloaded by {isc_user.user.username}.', request)
        # return response
    else:
        downloadable_url = zip_all_exported_users('export_sita_users')
        # ReadyToExport.objects.filter(is_downloaded=False).update(is_downloaded=True)
        response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)#, content_type="application/zip")
        response['Content-Disposition'] = "attachment; filename=export_sita_users.zip"
        response['Content-Type'] = "file/zip"
        logger.info(f'export_sita_users.zip downloaded by {isc_user.user.username}.', request)
        # response = {'result': 'success', 'url': downloadable_url}
    
    return response


@login_required(login_url="/login/")
def download_dirs_paths_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    downloadable_url = make_csv_of_all_paths(name="sita_all_dirs_paths")
    response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)
    response['Content-Disposition'] = "attachment; filename=sita_all_dirs_paths.csv"
    response['Content-Type'] = "text/csv"
    logger.info(f'sita_all_dirs_paths.csv downloaded by {isc_user.user.username}.', request)
    
    return response


@login_required(login_url="/login/")
def download_report_view(request, dd, *args, **kwargs):
    isc_user     = IscUser.objects.get(user=request.user)
    downloadable = None
    response     = None
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    downloadable_url = make_report_in_csv_format(dir_default_depth=dd, name="sita_user_dirs_report")
    response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)
    response['Content-Disposition'] = "attachment; filename=sita_user_dirs_report.csv"
    response['Content-Type'] = "text/csv"
    logger.info(f'sita_user_dirs_report.csv downloaded by {isc_user.user.username}.', request)
    
    return response


@login_required(login_url="/login/")
def entities_confirm_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = MftUser.objects.get(pk=request.POST.get('user') if request.POST.get('user') else id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            status_code = 200
            entity = ''
            dir_ = None
            response = {}
            try:
                entity = request.POST.get('entity')
                if entity == "mftuser":
                    # if MftUserTemp.objects.filter(username=mftuser.username).exists():
                    #     MftUserTemp.objects.filter(username=mftuser.username).delete()
                    MftUser.objects.filter(pk=id).update(is_confirmed=True)
                    logger.info(f'mftuser {mftuser.username} has been confirmed by {isc_user.user.username}.', request)
                    permissions = Permission.objects.filter(user=mftuser)
                    i = len(permissions)
                    confirmed = False
                    if i != 0:
                        for p in permissions:
                            if p.is_confirmed:
                                i -= 1
                        if i == 0:
                            confirmed = True
                    if confirmed:
                        # export_user(id=id, isc_user=isc_user)
                        export_user_with_paths(id=id, isc_user=isc_user)
                        logger.info(f'export file of mftuser {mftuser.username} is ready to download.', request)
                    response = {'result': 'success', 'confirmed': confirmed, 'mftuser': mftuser.username.replace('.', ''), 'id': mftuser.id}
                    # return JsonResponse(data=response, safe=False)
                elif entity == "directory":
                    dir_ = Directory.objects.get(pk=id)
                    permissions = Permission.objects.filter(user=mftuser, directory=dir_)
                    permissions.update(is_confirmed=True)
                    logger.info(f'all permissions of mftuser {mftuser.username} on {dir_.absolute_path} has been confirmed by {isc_user.user.username}.', request)
                    # for perm in permissions.iterator():
                    #     perm.is_confirmed = True
                    #     perm.save()
                    # dir_.is_confirmed = True
                    # dir_.save()
                    i = permissions.count()
                    confirmed = False
                    if mftuser.is_confirmed:
                        confirmed = False
                        if i != 0:
                            for p in permissions:
                                if p.is_confirmed:
                                    i -= 1
                            if i == 0:
                                confirmed = True
                                # export_user(id=mftuser.id, isc_user=isc_user)
                                export_user_with_paths(id=id, isc_user=isc_user)
                                logger.info(f'export file of mftuser {mftuser.username} is ready to download.', request)
                    response = {'result': 'success', 'confirmed': confirmed, 'mftuser': mftuser.username.replace('.', ''), 'id': mftuser.id}
                    # return JsonResponse(data=response, safe=False)
            except Exception as e:
                if entity == 'mftuser':
                    logger.info(f'mftuser {mftuser.username} confirmation encountered error.', request)
                else:
                    logger.info(f'confirmation of permissions of mftuser {mftuser.username} on {dir_.absolute_path} encountered error.', request)
                logger.error(e, request)
                status_code = 400
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)


# @login_required(login_url="/login/")
    # def mftuser_dismiss_changes_view(request, id, *args, **kwargs):
    #     isc_user = IscUser.objects.get(user=request.user)
    #     mftuser = get_object_or_404(MftUser, pk=id)
        
    #     if not isc_user.user.is_staff:
    #         logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
    #         return redirect('/error/401/')

    #     if request.is_ajax():
    #         if request.method == 'POST':
    #             if MftUserTemp.objects.filter(username=mftuser.username).exists():
    #                 mftuser_orig = MftUserTemp.objects.get(username=mftuser.username)
    #                 mftuser.description = mftuser_orig.description
    #                 # mftuser.username = mftuser_orig.username
    #                 # mftuser.password = mftuser_orig.password
    #                 # mftuser.firstname = mftuser_orig.firstname
    #                 # mftuser.lastname = mftuser_orig.lastname
    #                 mftuser.email = mftuser_orig.email
    #                 mftuser.officephone = mftuser_orig.officephone
    #                 mftuser.mobilephone = mftuser_orig.mobilephone
    #                 # mftuser.organization = mftuser_orig.organization
    #                 # mftuser.business = mftuser_orig.business
    #                 # mftuser.home_dir = mftuser_orig.home_dir
    #                 mftuser.ipaddr = mftuser_orig.ipaddr
    #                 mftuser.alias = mftuser_orig.alias
    #                 mftuser.is_confirmed = mftuser_orig.is_confirmed
    #                 mftuser.created_by = isc_user
    #                 mftuser.save()
    #                 mftuser.business.clear()
    #                 for b in mftuser_orig.business.all():
    #                     mftuser.business.add(b)
    #                 mftuser_orig.business.clear()
    #                 mftuser_orig.delete()
                
    #             response = {'result': 'success', 'dismissed': mftuser.username.replace('.', ''), 'id': mftuser.id}
    #             return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def mftuser_delete_view(request, id, *args, **kwargs):
    msg = None
    success = False
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.method == 'POST':
        # CustomerAccess.objects.filter(user=isc_user, target_id=id).delete()
        # Permission.objects.filter(user=mftuser).delete()
        # if not MftUserTemp.objects.filter(username=mftuser.username).exists():
        #     mftuser_temp = MftUserTemp(
        #         description=f'{mftuser.description}%deleted%',
        #         username=mftuser.username,
        #         password=mftuser.password,
        #         firstname=mftuser.firstname,
        #         lastname=mftuser.lastname,
        #         email=mftuser.email,
        #         officephone=mftuser.officephone,
        #         mobilephone=mftuser.mobilephone,
        #         organization=mftuser.organization,
        #         # business=mftuser.business,
        #         ipaddr=mftuser.ipaddr,
        #         # home_dir=mftuser.home_dir,
        #         alias=mftuser.alias,
        #         is_confirmed=mftuser.is_confirmed,
        #         created_by=isc_user
        #     )
        # else:
        #     mftuser_temp = MftUserTemp.objects.get(username=mftuser.username)
        #     mftuser_temp.description = f'{mftuser.description}%deleted%'
        #     mftuser_temp.business.clear()
        
        # mftuser_temp.save()
        # for b in mftuser.business.all():
        #     mftuser_temp.business.add(b)
        msg = f'کاربر {mftuser.username} موقتاً حذف شد، منتظر تأیید مدیر سیستم باشید.'
        mftuser.owned_business.clear()
        mftuser.used_business.clear()
        mftuser.delete()
        #TODO: delete invoices of this user
        logger.info(f'mftuser {mftuser.username} deleted by {isc_user.user.username}.', request)
        success = True
        # return redirect("/mftusers/")
    else:
        msg = f'آیا می خواهید کاربر <strong>{mftuser.username}</strong> را حذف نمائید؟'
    
    context = {
        'crud': 'delete',
        'msg': msg,
        'success': success,
        'mftuser': mftuser,
        'page_title': f'فرم حذف کاربر',
        'submit_action': 'حذف کاربر'
    }

    return render(request, "core/mftuser-form.html", context)


# @login_required(login_url="/login/")
    # def mftuser_restore_or_delete_view(request, id, *args, **kwargs):
    #     msg = None
    #     success = False
    #     isc_user = IscUser.objects.get(user=request.user)
    #     mftuser = get_object_or_404(MftUserTemp, pk=id)
    #     action = request.POST.get('action')
        
    #     if not isc_user.user.is_staff:
    #         logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
    #         return redirect('/error/401/')

    #     if request.is_ajax():
    #         if request.method == 'POST':
    #             try:
    #                 response = {'result': 'success', 'object': mftuser.username.replace('.', '')}
    #                 if action == 'restore':
    #                     description = mftuser.description.replace("%deleted%", "")
    #                     mftuser_new = MftUser(
    #                         username=mftuser.username,
    #                         password=mftuser.password,
    #                         firstname=mftuser.firstname,
    #                         lastname=mftuser.lastname,
    #                         email=mftuser.email,
    #                         officephone=mftuser.officephone,
    #                         mobilephone=mftuser.mobilephone,
    #                         organization=mftuser.organization,
    #                         # business=mftuser.business,
    #                         # home_dir=mftuser.home_dir,
    #                         ipaddr=mftuser.ipaddr,
    #                         # disk_quota=mftuser.disk_quota,
    #                         alias=mftuser.alias,
    #                         description=description,
    #                         is_confirmed=mftuser.is_confirmed,
    #                         created_by=isc_user
    #                     )
    #                     mftuser_new.save()
    #                     logger.info(f'mftuser {mftuser_new.username} restored by {isc_user.user.username}.', request)
    #                     for b in mftuser.business.all():
    #                         if Directory.objects.filter(relative_path=f'{b.code}/{mftuser_new.organization.directory_name}').exists():
    #                             mftuser_new.business.add(b)
    #                             create_default_permission(
    #                                 isc_user=isc_user,
    #                                 mftuser=mftuser_new,
    #                                 last_dir=Directory.objects.get(relative_path=f'{b.code}/{mftuser_new.organization.directory_name}'),
    #                                 home_dir=True,
    #                                 business=b,
    #                                 preconfirmed=True
    #                             )
    #                 mftuser.business.clear()
    #                 mftuser.delete()
    #                 return JsonResponse(data=response, safe=False)
    #             except Exception as e:
    #                 logger.error(e, request)
    #                 response = {'result': 'error'}
    #                 return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def rename_directory_view(request, did, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    dir_ = Directory.objects.get(pk=did)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            try:
                if isc_user.role.code == 'ADMIN' or dir_.created_by.department == isc_user.department:
                    old_name = dir_.name
                    new_name = request.POST.get('new_name')
                    dir_.name = new_name
                    dir_.relative_path = dir_.relative_path.replace(old_name, new_name)
                    dir_.save()
                    change_all_sub_directories_relative_path(dir_.children, dir_.relative_path)
                    logger.info(f'directory with id {dir_.id} renamed from {old_name} to {new_name} by {isc_user.user.username}.', request)
                    response = {'result': 'success', 'renamed_dir': dir_.id}
                else:
                    response = {'result': 'failed'}
            except Exception as e:
                logger.error(e, request)
                response = {'result': 'error'}
            
            return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def iscusers_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'users': IscUser.objects.all().order_by('user__username')
    }

    if request.is_ajax():
        if request.method == "GET":
            query = request.GET.get('q')
            filtered_iscusers = list(user.id for user in context['users'])
            if query != '':
                filtered_iscusers = list(user.id for user in context['users'] if query in user.user.username or query in user.department.description)
            return JsonResponse(data={"filtered_iscusers": filtered_iscusers}, safe=False)
    
    return render(request, "core/iscusers-list.html", context)


@login_required(login_url="/login/")
def iscusers_update_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == "POST":
            status_code = 200
            response = {'result': 'success'}
            try:
                subject_user = IscUser.objects.get(pk=id)
                action = request.POST.get('action')
                if action == 'activate':
                    subject_user.user.is_active = True
                    subject_user.user.save()
                    subject_user.save()
                    logger.info(f'iscuser {subject_user.user.username} activated by {isc_user.user.username}.', request)
                elif action == 'deactivate':
                    subject_user.user.is_active = False
                    subject_user.user.save()
                    subject_user.save()
                    logger.info(f'iscuser {subject_user.user.username} deactivated by {isc_user.user.username}.', request)
            except Exception as e:
                logger.error(e, request)
                status_code = 400
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)


@login_required(login_url='/login/')
def reset_password_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    msg = None
    success = None

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user = User.objects.get(username=form.cleaned_data['username'])
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            msg = "کلمه عبور با موفقیت ریست شد."
            success = True
            logger.info(f'{user.username} password has been reset by {isc_user.user.username}.', request)
        else:
            msg = form.errors
    else:
        form = ResetPasswordForm()

    context = {
        "form": form,
        "msg": msg,
        "success": success
    }

    return render(request, "accounts/reset-password.html", context)


@login_required(login_url="/login/")
def logs_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    logs = []
    id = 1
    for log in os.listdir(settings.LOGGING_PATH):
        with open(f'{settings.LOGGING_PATH}/{log}', mode='r', encoding='utf-8') as l:
            lines = l.readlines()
            log_name = log
            if log_name == 'portal.log':
                log_name += f'.{dt.now().strftime("%Y-%m-%d")}'
            logs.append({
                "id": id,
                "name": log_name,
                "text": lines
            })
            id += 1
    
    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'logs': logs
    }

    if request.is_ajax():
        if request.method == "GET":
            query = request.GET.get('q')
            filtered_logs = list(log['id'] for log in context['logs'])
            if query != '':
                filtered_logs = list(log['id'] for log in context['logs'] if query in log['name'])
            return JsonResponse(data={"filtered_logs": filtered_logs}, safe=False)
    
    return render(request, "core/logs-list.html", context)


@login_required(login_url="/login/")
def debug_mode_actions_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    # buck insertion into or correction in db
    # insert_into_db()
    # clean_up(flag='perm', action=False)
    # clean_up(flag='perm2', action=False)
    # clean_up(flag='dir', action=False)
    # clean_up(flag='dir3', action=False, bic_name="FIU")
    # clean_up(flag='inv', action=False)
    # dirs = Directory.objects.filter(name='Test')
    # refactor_directory(operation='rename', action=False, old_name='TRANSACTION', new_name='BANKIRAN')

    # invs = Invoice.objects.filter(id__in=[277, 278, 279, 280])
    # for inv in invs:
    #     ids = [int(i) for i in inv.permissions_list.split(',')[:-1]]
    #     for p in Permission.objects.filter(id__in=ids):
    #         print(p)
    #         if p.directory.name == 'accepted':
    #             p.directory = Directory.objects.get(pk=p.directory.parent)
    #             p.save()

    return redirect('/dashboard/')
