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

from invoice.models import Invoice, PreInvoice

from mftusers.utils import *

from core.models import *
from core.forms import *

import logging

logger = logging.getLogger(__name__)


@login_required(login_url="/login/")
def add_data_view(request, *args, **kwargs):
    msg      = None
    success  = False
    isc_user = IscUser.objects.get(user=request.user)
    username = str(isc_user.user.username)
    access   = str(isc_user.role.code)
    form     = AddBusinessForm(request.POST or None)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')
    
    if request.method == "POST":
        if form.is_valid():
            bus = BusinessCode(
                type_id=CodingType.objects.get(type=1009),
                code=form.cleaned_data.get("code"),
                description=form.cleaned_data.get("description"),
                address=form.cleaned_data.get("address")
            )
            bus.save()
            dir_ = Directory(
                name=bus.code,
                relative_path=bus.code,
                index_code=DirectoryIndexCode.objects.get(code=0),
                parent=0,
                business=bus,
                bic=BankIdentifierCode.objects.get(code='BMJI'),
                created_by=IscUser.objects.get(pk=1)
            )
            dir_.save()
            logger.info(f'{isc_user.user.username} add {bus.code} business.')
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
                logger.info(f'a directory in {ch_dir.absolute_path} created.')
                dir_.children += f'{ch_dir.id},'
            dir_.save()

            msg = f'پروژه/سامانه {bus.code} با موفقیت اضافه گردید.'
            success = True

            # return redirect("/login/")

        else:
            # 'اطلاعات ورودی صحیح نیست!'
            msg = form.errors

    context = {
        "username": username,
        "access": access,
        "form": form,
        "msg": msg,
        "success": success
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
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')
    
    all_buss = BusinessCode.objects.all().order_by('description')
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
def manage_data_view(request, uid=-1, *args, **kwargs):
    isc_user        = IscUser.objects.get(user=request.user)
    username        = str(isc_user.user.username)
    access          = str(isc_user.role.code)
    # mftusers        = MftUser.objects.filter(is_confirmed=False).order_by('username')
    # deleted_users   = MftUserTemp.objects.filter(description__icontains=f"%deleted%").order_by('username')
    # invoices        = Invoice.objects.filter(processed=False).order_by('created_at')
    invoices        = Invoice.objects.all().order_by('-created_at')
    pre_invoices    = PreInvoice.objects.all().order_by('-created_at')
    elements        = []
    new_users       = []
    changed_users   = []
    differences     = {}

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
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
                        mftuser = inv.get_mftuser()
                        buss = [bus.description for bus in mftuser.business.all()]
                        if query in mftuser.username or query in mftuser.alias or query in mftuser.organization.description or query in inv.serial_number or query in inv.created_by.user.username or query in inv.get_jalali_created_at() or query in buss:
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
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
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
            logger.info(f'mftuser {exported_user.mftuser.username} exported successfully.')
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
def sftp_user_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    rtes     = ReadyToExport.objects.all() if id == 0 else ReadyToExport.objects.filter(pk=id)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            response = {}
        files_list = []
        try:
            files_list = [re.webuser.path for re in rtes]
            export_users_with_sftp(files_list=files_list)
            if len(files_list) > 1:
                logger.info(f'all mftusers exported with sftp by {isc_user.user.username} successfully.')
            else:
                logger.info(f'mftuser with id {rtes.first().id} exported with sftp by {isc_user.user.username} successfully.')
            response = {'result': 'success'}
        except Exception as e:
            logger.error(e)
            response = {'result': 'error'}
        finally:
            return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def download_mftuser_view(request, id, *args, **kwargs):
    isc_user     = IscUser.objects.get(user=request.user)
    downloadable = None if id == 0 else ReadyToExport.objects.get(pk=id)
    response     = None
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if downloadable:
        # mime_type, _ = mimetypes.guess_type(downloadable.export.path)
        response = FileResponse(open(downloadable.generate_zip_file(name=downloadable.mftuser.username), 'rb'), as_attachment=True)#, content_type=mime_type)
        response['Content-Disposition'] = f"attachment; filename={downloadable.mftuser.username}.zip"
        response['Content-Type'] = "file/zip"
        logger.info(f'{downloadable.mftuser.username}.zip downloaded by {isc_user.user.username}.')
        # return response
    else:
        downloadable_url = zip_all_exported_users('export_sita_users')
        # ReadyToExport.objects.filter(is_downloaded=False).update(is_downloaded=True)
        response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)#, content_type="application/zip")
        response['Content-Disposition'] = "attachment; filename=export_sita_users.zip"
        response['Content-Type'] = "file/zip"
        logger.info(f'export_sita_users.zip downloaded by {isc_user.user.username}.')
        # response = {'result': 'success', 'url': downloadable_url}
    
    return response


@login_required(login_url="/login/")
def download_dirs_paths_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    downloadable_url = make_csv_of_all_paths(name="sita_all_dirs_paths")
    response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)
    response['Content-Disposition'] = "attachment; filename=sita_all_dirs_paths.csv"
    response['Content-Type'] = "text/csv"
    logger.info(f'sita_all_dirs_paths.csv downloaded by {isc_user.user.username}.')
    
    return response


@login_required(login_url="/login/")
def download_report_view(request, dd, *args, **kwargs):
    isc_user     = IscUser.objects.get(user=request.user)
    downloadable = None
    response     = None
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    downloadable_url = make_report_in_csv_format(dir_default_depth=dd, name="sita_user_dirs_report")
    response = FileResponse(open(downloadable_url, 'rb'), as_attachment=True)
    response['Content-Disposition'] = "attachment; filename=sita_user_dirs_report.csv"
    response['Content-Type'] = "text/csv"
    logger.info(f'sita_user_dirs_report.csv downloaded by {isc_user.user.username}.')
    
    return response


@login_required(login_url="/login/")
def entities_confirm_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = MftUser.objects.get(pk=request.POST.get('user') if request.POST.get('user') else id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
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
                    if MftUserTemp.objects.filter(username=mftuser.username).exists():
                        MftUserTemp.objects.filter(username=mftuser.username).delete()
                    MftUser.objects.filter(pk=id).update(is_confirmed=True)
                    logger.info(f'mftuser {mftuser.username} has been confirmed by {isc_user.user.username}.')
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
                        logger.info(f'export file of mftuser {mftuser.username} is ready to download.')
                    response = {'result': 'success', 'confirmed': confirmed, 'mftuser': mftuser.username.replace('.', ''), 'id': mftuser.id}
                    # return JsonResponse(data=response, safe=False)
                elif entity == "directory":
                    dir_ = Directory.objects.get(pk=id)
                    permissions = Permission.objects.filter(user=mftuser, directory=dir_)
                    permissions.update(is_confirmed=True)
                    logger.info(f'all permissions of mftuser {mftuser.username} on {dir_.absolute_path} has been confirmed by {isc_user.user.username}.')
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
                                logger.info(f'export file of mftuser {mftuser.username} is ready to download.')
                    response = {'result': 'success', 'confirmed': confirmed, 'mftuser': mftuser.username.replace('.', ''), 'id': mftuser.id}
                    # return JsonResponse(data=response, safe=False)
            except Exception as e:
                if entity == 'mftuser':
                    logger.info(f'mftuser {mftuser.username} confirmation encountered error.')
                else:
                    logger.info(f'confirmation of permissions of mftuser {mftuser.username} on {dir_.absolute_path} encountered error.')
                logger.error(e)
                status_code = 400
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)


@login_required(login_url="/login/")
def mftuser_dismiss_changes_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=id)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            if MftUserTemp.objects.filter(username=mftuser.username).exists():
                mftuser_orig = MftUserTemp.objects.get(username=mftuser.username)
                mftuser.description = mftuser_orig.description
                # mftuser.username = mftuser_orig.username
                # mftuser.password = mftuser_orig.password
                # mftuser.firstname = mftuser_orig.firstname
                # mftuser.lastname = mftuser_orig.lastname
                mftuser.email = mftuser_orig.email
                mftuser.officephone = mftuser_orig.officephone
                mftuser.mobilephone = mftuser_orig.mobilephone
                # mftuser.organization = mftuser_orig.organization
                # mftuser.business = mftuser_orig.business
                # mftuser.home_dir = mftuser_orig.home_dir
                mftuser.ipaddr = mftuser_orig.ipaddr
                mftuser.alias = mftuser_orig.alias
                mftuser.is_confirmed = mftuser_orig.is_confirmed
                mftuser.created_by = isc_user
                mftuser.save()
                mftuser.business.clear()
                for b in mftuser_orig.business.all():
                    mftuser.business.add(b)
                mftuser_orig.business.clear()
                mftuser_orig.delete()
            
            response = {'result': 'success', 'dismissed': mftuser.username.replace('.', ''), 'id': mftuser.id}
            return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def mftuser_delete_view(request, id, *args, **kwargs):
    msg = None
    success = False
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.method == 'POST':
        # CustomerAccess.objects.filter(user=isc_user, target_id=id).delete()
        # Permission.objects.filter(user=mftuser).delete()
        if not MftUserTemp.objects.filter(username=mftuser.username).exists():
            mftuser_temp = MftUserTemp(
                description=f'{mftuser.description}%deleted%',
                username=mftuser.username,
                password=mftuser.password,
                firstname=mftuser.firstname,
                lastname=mftuser.lastname,
                email=mftuser.email,
                officephone=mftuser.officephone,
                mobilephone=mftuser.mobilephone,
                organization=mftuser.organization,
                # business=mftuser.business,
                ipaddr=mftuser.ipaddr,
                # home_dir=mftuser.home_dir,
                alias=mftuser.alias,
                is_confirmed=mftuser.is_confirmed,
                created_by=isc_user
            )
        else:
            mftuser_temp = MftUserTemp.objects.get(username=mftuser.username)
            mftuser_temp.description = f'{mftuser.description}%deleted%'
            mftuser_temp.business.clear()
        
        mftuser_temp.save()
        for b in mftuser.business.all():
            mftuser_temp.business.add(b)
        msg = f'کاربر {mftuser.username} موقتاً حذف شد، منتظر تأیید مدیر سیستم باشید.'
        mftuser.business.clear()
        mftuser.delete()
        logger.info(f'mftuser {mftuser.username} deleted by {isc_user.user.username}.')
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


@login_required(login_url="/login/")
def mftuser_restore_or_delete_view(request, id, *args, **kwargs):
    msg = None
    success = False
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUserTemp, pk=id)
    action = request.POST.get('action')
    
    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            try:
                response = {'result': 'success', 'object': mftuser.username.replace('.', '')}
                if action == 'restore':
                    description = mftuser.description.replace("%deleted%", "")
                    mftuser_new = MftUser(
                        username=mftuser.username,
                        password=mftuser.password,
                        firstname=mftuser.firstname,
                        lastname=mftuser.lastname,
                        email=mftuser.email,
                        officephone=mftuser.officephone,
                        mobilephone=mftuser.mobilephone,
                        organization=mftuser.organization,
                        # business=mftuser.business,
                        # home_dir=mftuser.home_dir,
                        ipaddr=mftuser.ipaddr,
                        # disk_quota=mftuser.disk_quota,
                        alias=mftuser.alias,
                        description=description,
                        is_confirmed=mftuser.is_confirmed,
                        created_by=isc_user
                    )
                    mftuser_new.save()
                    logger.info(f'mftuser {mftuser_new.username} restored by {isc_user.user.username}.')
                    for b in mftuser.business.all():
                        if Directory.objects.filter(relative_path=f'{b.code}/{mftuser_new.organization.directory_name}').exists():
                            mftuser_new.business.add(b)
                            create_default_permission(
                                isc_user=isc_user,
                                mftuser=mftuser_new,
                                last_dir=Directory.objects.get(relative_path=f'{b.code}/{mftuser_new.organization.directory_name}'),
                                home_dir=True,
                                business=b,
                                preconfirmed=True
                            )
                mftuser.business.clear()
                mftuser.delete()
                return JsonResponse(data=response, safe=False)
            except Exception as e:
                print(e)
                response = {'result': 'error'}
                return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def iscusers_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
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
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
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
                    logger.info(f'iscuser {subject_user.user.username} activated by {isc_user.user.username}.')
                elif action == 'deactivate':
                    subject_user.user.is_active = False
                    subject_user.user.save()
                    subject_user.save()
                    logger.info(f'iscuser {subject_user.user.username} deactivated by {isc_user.user.username}.')
            except Exception as e:
                logger.error(e)
                status_code = 400
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)

