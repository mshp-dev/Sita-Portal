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
def mftuser_create_view(request, *args, **kwargs):
    msg     = None
    success = False
    mftuser = None
    isc_user = IscUser.objects.get(user=request.user)
    
    if request.is_ajax():
        if request.method == "GET":
            firstname = request.GET.get('fn')
            lastname = request.GET.get('ln')
            bic_desc = request.GET.get('bic')
            if BankIdentifierCode.objects.filter(description=bic_desc).exists():
                bic = BankIdentifierCode.objects.get(description=bic_desc)
                delimiter = '_' if bic.code == 'ISC' else '.'
                username = make_username(firstname, lastname, delimiter)
                return JsonResponse(data={'username': username}, safe=False)
            else:
                return JsonResponse(data={'username': 'null'}, safe=False)
    
    if isc_user.role.code == 'CUSTOMER':
        orgs = [acc.access_on_bic for acc in CustomerBank.objects.filter(user=isc_user).order_by('access_on_bic')]
        buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
    elif isc_user.role.code == 'OPERATION':
        # orgs = [bic for bic in BankIdentifierCode.objects.all().order_by('description')]
        orgs = [bic for bic in BankIdentifierCode.objects.filter(code='ISC')]
        if OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).exists():
            buss = [BusinessCode.objects.get(pk=bus.access_on_bus.id) for bus in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).order_by('access_on_bus')]
        else:
            buss = [BusinessCode.objects.get(code='NO_PROJECT'),]
    elif isc_user.role.code == 'ADMIN':
        orgs = [bic for bic in BankIdentifierCode.objects.all().order_by('description')]
        buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
    
    form = MftUserForm(request.POST or None, request=request)
    form.fields['organization'].choices = [(bic.id, bic) for bic in orgs]
    form.fields['business'].choices = [(bus.id, bus) for bus in buss]
    
    if request.method == "POST":
        if form.is_valid():
            mftuser = form.save(commit=False)
            mftuser.password = 'Isc@12345678'
            # mftuser.home_dir = mftuser.business.code #/f'{}{mftuser.organization.directory_name}'
            mftuser.created_by = isc_user
            mftuser.created_at = timezone.now()
            mftuser.save()
            logger.info(f'mftuser {mftuser.username} created by {isc_user.user.username}.')
            bus_error = ''
            no_project_bus = BusinessCode.objects.get(code='NO_PROJECT')
            if str(no_project_bus.id) in form.cleaned_data.get('business'):
                logger.info(f'mftuser {mftuser.username} has NO_PROJECT access.')
                mftuser.description = 'بدون پروژه/سامانه'
            else:
                for b in form.cleaned_data.get('business'):
                    bus = BusinessCode.objects.get(id=int(b))
                    if Directory.objects.filter(relative_path=f'{bus.code}/{mftuser.organization.directory_name}').exists():
                        mftuser.business.add(bus)
                        # create_default_permission(
                        #     isc_user=isc_user,
                        #     mftuser=mftuser,
                        #     last_dir=Directory.objects.get(relative_path=f'{bus.code}/{mftuser.organization.directory_name}'),
                        #     business=bus,
                        #     home_dir=True
                        # )
                        logger.info(f'access on business {bus.code} for {mftuser.username} has been created.')
                    else:
                        bus_error += f'<p>اختصاص پروژه/سامانه {bus.code} میسر نیست.<p>'
                        logger.warning(f'access on business {bus.code} for {mftuser.username} has not been created.')
                
                # if mftuser.organization.code == 'ISC':
                    # mftuser.description = str(isc_user.department)
                # else:
                    # mftuser.description = f'{mftuser.organization}'
                buss = ''
                for bus in mftuser.business.all():
                    buss += f'{str(bus)}،'
                project = "سامانه های" if mftuser.business.all().count() > 1 else "سامانه"
                mftuser.description = f'{project} {buss[:-1]}'
            mftuser.save()
            msg = f'<p>کاربر {mftuser.username} ایجاد شد.<p><br >{bus_error}'
            success = True
        else:
            msg = form.errors
    
    context = {
        'crud': 'create',
        'form': form,
        'msg': msg,
        'buss': buss,
        'success': success,
        'new_user_id': -1 if mftuser is None else mftuser.id,
        'page_title': 'فرم ایجاد کاربر FTP',
        'submit_action': 'ایجاد کاربر'
    }

    return render(request, "core/mftuser-form.html", context)


@login_required(login_url="/login/")
def directories_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    context = {}

    if isc_user.role.code == 'CUSTOMER':
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            dir_name = request.POST.get('name')
            pid = int(request.POST.get('parent'))
            if not Directory.objects.filter(name=dir_name, parent=pid).exists():
                parent = Directory.objects.get(pk=pid)
                new_path = f'{parent.relative_path}/{dir_name}'
                new_index = DirectoryIndexCode.objects.get(code=str(int(parent.index_code.code) - 1))
                new_dir = Directory(
                    name=dir_name,
                    parent=pid,
                    relative_path=new_path,
                    bic=parent.bic,
                    business=parent.business,
                    created_by=isc_user,
                    index_code=new_index
                )
                new_dir.save()
                #TODO: if parent dir did not have any children old
                #      permissions more than list should be delete
                logger.info(f'directory {new_dir.absolute_path} by {isc_user.user.username} has been created.')
                parent.children = f'{parent.children}{new_dir.id},'
                parent.save()
                serialized_data = {
                    'result': 'success',
                    'new_dir': model_to_dict(new_dir)
                }
            else:
                serialized_data = {
                    'result': 'error',
                    'message': 'دایرکتوری با این نام موجود است!'
                }
            return JsonResponse(data=serialized_data, safe=False)
        elif request.method == 'GET':
            query = request.GET.get('q')
            if query:
                if query != '':
                    response = {
                        "filtered_directories": get_parent_dirs(
                            [elem['dir'].id for elem in get_all_dirs(isc_user, query=query, pretify=False)]
                        )
                    }
                else:
                    response = {
                        "filtered_directories": [elem['dir'].id for elem in get_all_dirs(isc_user)]
                    }
            else:
                response = {"result": "empty"}
                if Directory.objects.filter(created_by=isc_user, is_confirmed=False).exists():
                    dirs = Directory.objects.filter(created_by=isc_user, is_confirmed=False).order_by('-created_at')
                    dirs_str = ''
                    for d in dirs.values('id'):
                        dirs_str += f'{str(d["id"])},'
                    if PreInvoice.objects.filter(directories_list=dirs_str).exists():
                        response["result"] = "exists"
                    else:
                        response["result"] = "ok"
                        response["dirs_list"] = dirs_str
                    # elif PreInvoice.objects.filter(directories_list__icontains=dirs_str).exists():
                    #     response["result"] = "exists"
            
            return JsonResponse(data=response, safe=False)
        
    elements = get_all_dirs(isc_user)
    
    context = {
        'elements':elements,
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code)
    }
    
    return render(request, "core/directories-view.html", context)


@login_required(login_url="/login/")
def mftusers_list_view(request, *args, **kwargs):
    # paginate_by = 2
    # page = request.GET.get('page', 1)
    isc_user = IscUser.objects.get(user=request.user)
    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'view': 'create' if 'create' in request.path else '',
        'title': 'ایجاد/تغییر کاربر سیتا' if 'create' in request.path else 'اختصاص دسترسی به کاربران',
        'desc': 'در اینجا می توانید کاربران بانک ها و سازمان ها را در سامانه سیتا تعریف نمائید' if 'create' in request.path else 'در اینجا می توانید سطح دسترسی کاربران را تعیین نمائید'
    }

    if str(isc_user.role.code) == 'CUSTOMER':
        accesses = CustomerBank.objects.filter(user=isc_user)
        u_bics = [a.access_on_bic for a in accesses]
        mftusers = MftUser.objects.filter(organization__in=u_bics).order_by('username')
    elif str(isc_user.role.code) == 'OPERATION':
        if OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).exists():
            accesses = OperationBusiness.objects.filter(user=isc_user, owned_by_user=True)
            u_buss = [a.access_on_bus for a in accesses]
            mftusers = MftUser.objects.filter(business__in=u_buss).order_by('username').distinct()
        else:
            mftusers = MftUser.objects.filter(created_by=isc_user).order_by('username')
    else:
        mftusers = MftUser.objects.all().order_by('username')

    context['users'] = mftusers
    # context['admin_view'] = True if isc_user.user.is_staff else False

    if request.is_ajax():
        if request.method == "GET":
            # mftusers = MftUser.objects.filter(username__icontains=request.GET.get('q'))
            query = request.GET.get('q')
            filtered_mftusers = list(user.id for user in context['users'].order_by('username'))
            if query != '':
                filtered_mftusers = list(user.id for user in context['users'].order_by('username') if query in user.username or query in user.alias or query in user.organization.description) # or query in user.business.description
            return JsonResponse(data={"filtered_mftusers": filtered_mftusers}, safe=False)
            # context['users'] = filtered_mftusers
            # html = render_to_string(
            #     template_name="includes/users-list.html", context=context
            # )
            # data_dict = {"html_from_view": html}
            # return JsonResponse(data=data_dict, safe=False)
    
    return render(request, "core/mftusers-list.html", context)


@login_required(login_url="/login/")
def mftuser_details_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    # bus = BusinessCode.objects.filter(code=mftuser.business.all())
    msg = None
    
    #  if mftuser.organization.code == '_ISC' else get_specific_root_dir(mftuser.organization.code)
    
    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=mftuser.business.all()).exists() and mftuser.created_by != isc_user:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if isc_user.role.code == 'CUSTOMER':
        orgs = [acc.access_on_bic for acc in CustomerBank.objects.filter(user=isc_user)]
        buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
    elif isc_user.role.code == 'OPERATION':
        orgs = [acc for acc in BankIdentifierCode.objects.all().order_by('description')]
        if OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).exists():
            buss = [bus.access_on_bus for bus in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).order_by('access_on_bus__description')]
        else:
            buss = [BusinessCode.objects.get(code='NO_PROJECT'),]
    elif isc_user.role.code == 'ADMIN':
        orgs = [bic for bic in BankIdentifierCode.objects.all().order_by('description')]
        buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
    
    form = MftUserForm(request.POST or None, instance=mftuser, request=request)
    form.fields['organization'].choices = [(bic.id, bic) for bic in orgs]
    form.fields['business'].choices = [(bus.id, bus) for bus in buss]

    # update mftuser
    if request.method == 'POST':
        if form.is_valid():
            # form.save()
            mftuser = form.save(commit=False)
            mftuser_origin = MftUser.objects.get(username=mftuser.username)
            if not MftUserTemp.objects.filter(username=mftuser_origin.username).exists():
                mftuser_temp = MftUserTemp(
                    description=mftuser_origin.description,
                    username=mftuser_origin.username,
                    password=mftuser_origin.password,
                    firstname=mftuser_origin.firstname,
                    lastname=mftuser_origin.lastname,
                    email=mftuser_origin.email,
                    officephone=mftuser_origin.officephone,
                    mobilephone=mftuser_origin.mobilephone,
                    organization=mftuser_origin.organization,
                    # business=mftuser_origin.business,
                    # home_dir=mftuser_origin.home_dir,
                    ipaddr=mftuser_origin.ipaddr,
                    # disk_quota=mftuser_origin.disk_quota,
                    alias=mftuser_origin.alias,
                    created_by=isc_user
                )
            else:
                mftuser_temp = MftUserTemp.objects.get(username=mftuser_origin.username)
                # mftuser_temp.description=mftuser_origin.description
                # mftuser_temp.username=mftuser_origin.username,
                # mftuser_temp.password=mftuser_origin.password,
                # mftuser_temp.firstname=mftuser_origin.firstname,
                # mftuser_temp.lastname=mftuser_origin.lastname,
                mftuser_temp.email=mftuser_origin.email,
                mftuser_temp.officephone=mftuser_origin.officephone
                mftuser_temp.mobilephone=mftuser_origin.mobilephone
                # mftuser_temp.organization=mftuser_origin.organization,
                # mftuser_temp.business=mftuser_origin.business,
                # mftuser_temp.home_dir=mftuser_origin.home_dir,
                mftuser_temp.ipaddr=mftuser_origin.ipaddr
                # mftuser_temp.created_by=mftuser_origin.created_by,
                # mftuser_temp.disk_quota=mftuser_origin.disk_quota,
                mftuser_temp.alias=mftuser_origin.alias
                mftuser_temp.business.clear()
            mftuser_temp.save()
            logger.info(f'mftuser {mftuser_origin.username} edited by {isc_user.user.username}.')
            no_project_bus = BusinessCode.objects.get(code='NO_PROJECT')
            if str(no_project_bus.id) in form.cleaned_data.get('business'):
                mftuser_temp.business.clear()
                Permission.objects.filter(directory__parent=0).delete()
                mftuser_origin.business.clear()
                logger.info(f'mftuser {mftuser.username} has NO_PROJECT access.')
                mftuser_origin.is_confirmed = False
                mftuser_origin.email = mftuser.email
                mftuser_origin.description = mftuser.description
                mftuser_origin.officephone = mftuser.officephone
                mftuser_origin.mobilephone = mftuser.mobilephone
                mftuser_origin.alias = mftuser.alias
                mftuser_origin.ipaddr = mftuser.ipaddr
                # mftuser_origin.disk_quota=mftuser.disk_quota
                mftuser_origin.modified_at = timezone.now()
                mftuser_origin.save()
                msg = '<strong>اطلاعات کاربر بروزرسانی شد</strong>'
                success = True
            else:
                for bus in mftuser_origin.business.all():
                    mftuser_temp.business.add(bus)
                dirs = [Directory.objects.get(business=b, parent=0) for b in mftuser_temp.business.all()]
                dirs_ = []
                for d in dirs:
                    dirs_.append(d)
                    dirs_.append(Directory.objects.get(relative_path=f'{d.business.code}/{mftuser_origin.organization.directory_name}'))
                Permission.objects.filter(directory__parent=0).delete()
                mftuser_origin.business.clear()
                for b in form.cleaned_data.get('business'):
                    bus = BusinessCode.objects.get(id=int(b))
                    if Directory.objects.filter(relative_path=f'{bus.code}/{mftuser_origin.organization.directory_name}').exists():
                        mftuser_origin.business.add(bus)
                        logger.info(f'{isc_user.user.username} added business {bus} for mftuser {mftuser_origin.username}.')
                        # create_default_permission(
                        #     isc_user=isc_user,
                        #     mftuser=mftuser_origin,
                        #     last_dir=Directory.objects.get(relative_path=f'{bus.code}/{mftuser_origin.organization.directory_name}'),
                        #     business=bus,
                        #     home_dir=True
                        # )
                        mftuser_origin.is_confirmed = False
                        mftuser_origin.email = mftuser.email
                        mftuser_origin.description = mftuser.description
                        mftuser_origin.officephone = mftuser.officephone
                        mftuser_origin.mobilephone = mftuser.mobilephone
                        mftuser_origin.alias = mftuser.alias
                        mftuser_origin.ipaddr = mftuser.ipaddr
                        # mftuser_origin.disk_quota=mftuser.disk_quota
                        mftuser_origin.modified_at = timezone.now()
                        mftuser_origin.save()
                        msg = '<strong>اطلاعات کاربر بروزرسانی شد</strong>'
                        success = True
                    else:
                        logger.error(f'directory in {bus.code}/{mftuser_origin.organization.directory_name} does not exists.')
                        mftuser_origin.email = mftuser_temp.email
                        mftuser_origin.description = mftuser_temp.description
                        mftuser_origin.officephone = mftuser_temp.officephone
                        mftuser_origin.mobilephone = mftuser_temp.mobilephone
                        mftuser_origin.alias = mftuser_temp.alias
                        mftuser_origin.ipaddr = mftuser_temp.ipaddr
                        # mftuser_origin.disk_quota=mftuser_temp.disk_quota
                        mftuser_origin.modified_at = mftuser_temp.modified_at
                        mftuser_origin.save()
                        mftuser_temp.delete()
                        msg = '<strong>امکان تغییر پروژه/سامانه کاربر نمی باشد</strong>'
        else:
            msg = form.errors
    # else:
    #     if MftUserTemp.objects.filter(username=mftuser.username).exists():

    confirmed = False
    if mftuser.is_confirmed:
        permissions = Permission.objects.filter(user=mftuser)
        i = len(permissions)
        if i != 0:
            for p in permissions:
                if p.is_confirmed:
                    i -= 1
            if i == 0:
                confirmed = True
    
    context = {
        'msg': msg,
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'mftuser': mftuser,
        "buss": buss,
        'used_buss': mftuser.get_used_business(obj=True),
        'confirmed': confirmed,
        'form': form
    }

    return render(request, "core/mftuser-details.html", context)


@login_required(login_url="/login/")
def mftuser_access_view(request, uid, rid=-1, dir_name="", *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=uid)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    # bus = BusinessCode.objects.get(code=mftuser.business.code)
    # buss = mftuser.business.all()
    owned_buss = [ob.access_on_bus for ob in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).order_by('access_on_bus')]
    elements = None
    used_buss = None
    
    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=owned_buss).exists() and mftuser.created_by != isc_user:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        # if request.method == 'POST':
            #     if not Directory.objects.filter(name=dir_name, parent=pid).exists():
            #         parent = Directory.objects.get(pk=pid)
            #         new_path = f'{parent.relative_path}/{dir_name}'
            #         new_index = DirectoryIndexCode.objects.get(code=str(int(parent.index_code.code) - 1))
            #         new_dir = Directory(
            #             name=dir_name,
            #             parent=pid,
            #             relative_path=new_path,
            #             bic=parent.bic,
            #             business=parent.business,
            #             created_by=isc_user,
            #             index_code=new_index
            #         )
            #         new_dir.save()
            #         logger.info(f'directory {new_dir.absolute_path} by {isc_user.user.username} has been created.')
            #         parent.children = f'{parent.children}{new_dir.id},'
            #         parent.save()
            #         # CustomerAccess.objects.create(
            #         #     user=isc_user,
            #         #     access_on=CustomerAccessCode.objects.get(code='Directory'),
            #         #     target_id=new_dir.id,
            #         #     access_type=CustomerAccessType.objects.get(code='MODIFIER'),
            #         #     created_at=timezone.now()
            #         # )
            #         create_default_permission(
            #             isc_user=isc_user,
            #             mftuser=mftuser,
            #             last_dir=new_dir
            #         )
            #         # check_parents_permission(
            #         #     isc_user=isc_user,
            #         #     mftuser=mftuser,
            #         #     parent=new_dir.parent
            #         # )
            #         # data = {'id': new_dir.id, 'business': 'Name': new_dir.name, 'path': new_dir.relative_path}
            #         serialized_data = {
            #             'result': 'success',
            #             'new_dir': model_to_dict(new_dir)
            #         }
            #     else:
            #         serialized_data = {
            #             'result': 'error',
            #             'message': 'دایرکتوری با این نام موجود است!'
            #         }
            #     return JsonResponse(data=serialized_data, safe=False)
        if request.method == 'GET':
            query = request.GET.get('q')
            if query != '':
                response = {
                    "filtered_directories": get_parent_dirs(
                        [elem['dir'].id for elem in get_all_dirs(isc_user, query=query, pretify=False)]
                    )
                }
            else:
                response = {
                    "filtered_directories": [elem['dir'].id for elem in get_all_dirs(isc_user)]
                }
            return JsonResponse(data=response, safe=False)

    if isc_user.role.code == 'ADMIN':
        if rid != -1:
            buss = list(mftuser.business.all())
            u_buss_perms = Permission.objects.filter(~Q(directory__business__in=buss), directory__parent=0, user=mftuser).values('directory__business')
            for ubp in u_buss_perms:
                buss.append(BusinessCode.objects.get(code=ubp['directory__business']))
            elements = get_specific_root_dir(buss, bic)
        else:
            elements = get_all_dirs(isc_user)
    else:
        buss = []
        if isc_user.role.code == 'OPERATION':
            o_buss = OperationBusiness.objects.filter(user=isc_user, owned_by_user=False).order_by('access_on_bus')
            if o_buss.count() > 0:
                used_buss = [{'value': f'{ob.access_on_bus.id}', 'name': f'{ob.access_on_bus}'} for ob in o_buss]
            for bus in mftuser.business.all():
                if bus in owned_buss:
                    buss.append(bus)
        elif isc_user.role.code == 'CUSTOMER':
            buss = mftuser.business.all()
        elements = get_specific_root_dir(buss, bic)

    permissions = Permission.objects.filter(user=mftuser)
    confirmed = False
    i = len(permissions)
    if i != 0:
        for p in permissions:
            if p.is_confirmed:
                i -= 1
        if i == 0:
            confirmed = True
    
    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'mftuser': mftuser,
        'confirmed': confirmed,
        'elements': elements,
        'used_buss': used_buss
    }

    return render(request, "core/mftuser-access.html", context)


@login_required(login_url="/login/")
def mftuser_used_business_access_view(request, uid, bid=-1, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    used_buss = BusinessCode.objects.filter(pk=bid)
    mftuser = get_object_or_404(MftUser, pk=uid)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    elements = None
    
    if not isc_user.user.is_staff and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=used_buss).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if isc_user.role.code != 'OPERATION':
        return redirect(f'/mftuser/{mftuser.id}/directories/')

    elements = get_specific_root_dir(used_buss, bic)    
    permissions = Permission.objects.filter(user=mftuser)
    confirmed = False
    i = len(permissions)
    if i != 0:
        for p in permissions:
            if p.is_confirmed:
                i -= 1
        if i == 0:
            confirmed = True
    
    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'mftuser': mftuser,
        'confirmed': confirmed,
        'elements': elements,
        'used_bus': used_buss.first()
    }

    return render(request, "core/mftuser-used-business-access.html", context)


@login_required(login_url="/login/")
def mftuser_permissions_view(request, uid, did, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = MftUser.objects.get(pk=uid)
    directory = Directory.objects.get(pk=did)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    # bus = BusinessCode.objects.get(code=mftuser.business.code)

    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=mftuser.business.all()).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        # if request.method == 'POST':
            #     old_permissions = []
            #     splited = []
            #     status_code = 200
            #     response = {}
            #     try:
            #         permissions = request.POST.get('permissions')
            #         splited = [int(t) for t in permissions.split(',')[:-1]]
            #         old_permissions = [ae for ae in Permission.objects.filter(user=mftuser, directory=directory)]
            #         for op in old_permissions:
            #             if op.permission not in splited:
            #                 if isc_user.role.code != 'ADMIN':
            #                     if op.permission == 1: #Download (Read)
            #                         Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete()   #Checksum
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete() #List
            #                         splited.remove(128)
            #                     elif op.permission == 2: #Upload (Write)
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete() #Checksum
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete() #List
            #                         Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()   #Overwrite
            #                         Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
            #                         splited.remove(512)
            #                         splited.remove(1024)
            #                     elif op.permission == 32: #Delete (Modify)
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=1).delete()    #Download
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=2).delete()    #Upload
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete()  #Checksum
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete()  #List
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()  #Overwrite
            #                         # Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete() #Append
            #                         Permission.objects.filter(user=mftuser, directory=directory, permission=8).delete()      #Rename
            #                         splited.remove(8)
            #                 op.delete()
            #         for pv in splited:
            #             perm = DirectoryPermissionCode.objects.get(value=pv)
            #             if not Permission.objects.filter(user=mftuser, directory=directory, permission=perm.value).exists():
            #                 perm = Permission(
            #                     user=mftuser,
            #                     directory=directory,
            #                     permission=perm.value,
            #                     created_by=isc_user
            #                 )
            #                 perm.save()
            #                 check_parents_permission(
            #                     isc_user=isc_user,
            #                     mftuser=mftuser,
            #                     parent=directory.parent
            #                     # permission=perm.value,
            #                 )
            #             if pv == 1: #Download (Read)
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=256, #List
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=128, #Checksum
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=1024, #Append
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #             elif pv == 2: #Upload (Write)
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=256, #List
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=128, #Checksum
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=1024, #Append
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=512).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=512, #Overwrite
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #             elif pv == 32: #Delete (Modify)
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=256, #List
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=128, #Checksum
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=512).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=512, #Overwrite
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=8).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=8, #Rename
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=1024, #Append
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=1).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=1, #Download
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #                 if not Permission.objects.filter(user=mftuser, directory=directory, permission=2).exists():
            #                     perm = Permission(
            #                         user=mftuser,
            #                         directory=directory,
            #                         permission=2, #Upload
            #                         created_by=isc_user
            #                     )
            #                     perm.save()
            #             # elif pv == 0: #Subdirectory (ایجاد پوشه)
            #             #     reduce_parents_permission()
            #         logger.info(f'permission of directory {directory.absolute_path} for mftuser {mftuser.username} changed to {splited} by {isc_user.user.username}.')
            #         response = {'result': 'success'}
            #     except Exception as e:
            #         print(e)
            #         status_code = 400
            #         logger.error(f'permission change on directory {directory.absolute_path} to {splited} by {isc_user.user.username} encountered with error.')
            #         response = {'result': 'error', 'perms': [str(op) + "," for op in old_permissions]}
            #     finally:
            #         return JsonResponse(data=response, safe=False, status=status_code)
        if request.method == 'GET':
            permissions = Permission.objects.filter(user=mftuser, directory=directory)
            response = [{'value': perm.permission} for perm in permissions] if permissions != None else [{}]
            i = len(permissions)
            if i != 0:
                for p in permissions:
                    if p.is_confirmed:
                        i -= 1
                if i == 0:
                    response.append({'value': 'isconfirmed'})
                else:
                    response.append({'value': 'notconfirmed'})
            else:
                response.append({'value': 'notconfirmed'})
            return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def mftuser_atomic_permission_view(request, uid, did, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = MftUser.objects.get(pk=uid)
    directory = Directory.objects.get(pk=did)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)

    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=mftuser.business.all()).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            try:
                response = {}
                permissions = request.POST.get('permissions')
                splited = [int(t) for t in permissions.split(',')[:-1]]
                action = request.POST.get('action')
                if directory.children != '':
                    logger.warn(f'{isc_user.user.username} trying to change permission of directory {directory.absolute_path} for mftuser {mftuser.username}.')
                    logger.error(f'permission of directory {directory.absolute_path} (with children) could not be more than list.')
                    response = {
                        'result': 'error',
                        'message': 'به علت وجود پوشه داخل این دایرکتوری نمی توانید در این مسیر دسترسی خواندن/نوشتن/حذف فایل بدهید.'
                    }
                    return JsonResponse(data=response, safe=False)
                else:
                    if action == 'add':
                        splited.append(0) #ApplyToSubfolder
                if action == 'remove':
                    for pv in splited:
                        if Permission.objects.filter(user=mftuser, directory=directory, permission=pv).exists():
                            Permission.objects.filter(user=mftuser, directory=directory, permission=pv).delete()
                        if pv == 0: #Create Folder
                            Permission.objects.filter(user=mftuser, directory=directory, permission=4).delete()     #Create
                        elif pv == 1: #Download (Read)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                        elif pv == 2: #Upload (Write)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()   #Overwrite
                            Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                        elif pv == 32: #Delete (Modify)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=8).delete()     #Rename
                        elif pv == 256: #List
                            Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete()   #Checksum
                        remaining_perms = Permission.objects.filter(user=mftuser, directory=directory)
                        if remaining_perms.count() <= 2:
                            remaining_perms_list = [p['permission'] for p in remaining_perms.values('permission').distinct()]
                            if '128' in remaining_perms_list or '256' in remaining_perms_list: # if just List or Append or both remained
                                remaining_perms.delete()
                    logger.info(f'permission {splited} of directory {directory.absolute_path} for mftuser {mftuser.username} removed by {isc_user.user.username}.')
                elif action == 'add':
                    # check_parents_permission(
                    #     isc_user=isc_user,
                    #     mftuser=mftuser,
                    #     parent=directory.parent
                    #     # permission=perm.value,
                    # )
                    for pv in splited:
                        if not Permission.objects.filter(user=mftuser, directory=directory, permission=pv).exists():
                            perm = Permission(
                                user=mftuser,
                                directory=directory,
                                permission=pv,
                                created_by=isc_user
                            )
                            perm.save()
                        if pv == 0: #ApplyToSubfolder
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=256, #List
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=128, #Checksum
                                    created_by=isc_user
                                )
                                perm.save()
                        elif pv == 1: #Download (Read)
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=256, #List
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=128, #Checksum
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=1024, #Append
                                    created_by=isc_user
                                )
                                perm.save()
                        elif pv == 2: #Upload (Write)
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=256, #List
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=128, #Checksum
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=1024, #Append
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=512).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=512, #Overwrite
                                    created_by=isc_user
                                )
                                perm.save()
                        elif pv == 4: #Create (Subfolder)
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=256, #List
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=128, #Checksum
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=0).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=0, #ApplySubfolder
                                    created_by=isc_user
                                )
                                perm.save()
                        elif pv == 32: #Delete (Modify)
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=256, #List
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=128).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=128, #Checksum
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=512).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=512, #Overwrite
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=8).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=8, #Rename
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=1024).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=1024, #Append
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=1).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=1, #Download
                                    created_by=isc_user
                                )
                                perm.save()
                            if not Permission.objects.filter(user=mftuser, directory=directory, permission=2).exists():
                                perm = Permission(
                                    user=mftuser,
                                    directory=directory,
                                    permission=2, #Upload
                                    created_by=isc_user
                                )
                                perm.save()
                    logger.info(f'permission of directory {directory.absolute_path} for mftuser {mftuser.username} changed to {splited} by {isc_user.user.username}.')
                response = {'result': 'success'}
            except Exception as e:
                logger.error(e)
                logger.error(f'permission change on directory {directory.absolute_path} to {splited} by {isc_user.user.username} encountered with error.')
                response = {'result': 'error', 'message': 'مشکلی پیش آمده است، با مدیر سیستم تماس بگیرید!'}
            finally:
                return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def transfer_permissions_view(request, *args, **kwargs):
    msg      = ''
    success  = False
    isc_user = IscUser.objects.get(user=request.user)
    username = str(isc_user.user.username)
    access   = str(isc_user.role.code)
    form     = TransferPermissionsForm(request.POST or None, request=request)

    # if not isc_user.user.is_staff:
    #     logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
    #     return redirect('/error/401/')
    
    if request.is_ajax():
        if request.method == 'POST':
            pass
        elif request.method == 'GET':
            pass

    if request.method == "POST":
        if form.is_valid():
            orig_user = MftUser.objects.get(username=form.cleaned_data.get("origin_mftuser"))
            dest_user = MftUser.objects.get(username=form.cleaned_data.get("destination_mftuser"))
            old_permissions = Permission.objects.filter(user=dest_user)
            confirmed_permissions = list(old_permissions.filter(is_confirmed=True).values_list('directory', flat=True, named=False).distinct())
            # confirmed_permissions_path = confirmed_permissions.filter(is_confirmed=True).values('directory__relative_path').distinct()
            # confirmed_permissions_path_list = [cpp['directory__relative_path'] for cpp in confirmed_permissions_path]
            old_permissions.delete()
            permissions = Permission.objects.filter(user=orig_user)
            for perm in permissions:
                Permission.objects.create(
                    created_at=timezone.now(),
                    created_by=isc_user,
                    user=dest_user,
                    directory=perm.directory,
                    permission=perm.permission,
                    is_confirmed=True if perm.directory.id in confirmed_permissions else False
                )
                logger.info(f'permission of directory {perm.directory.absolute_path} for mftuser {dest_user.username} changed to {perm.permission} by {isc_user.user.username}.')
            # Permission.objects.filter(user=dest_user, directory__relative_path__in=confirmed_permissions_path_list).update(is_confirmed=True)
            logger.info(f'all permissions of {orig_user} to {dest_user} transfered successfully by {isc_user.user.username}')
            msg = f'انتقال دسترسی های {form.cleaned_data.get("origin_mftuser")} به {form.cleaned_data.get("destination_mftuser")} با موفقیت انجام شد.'
            success = True
            # return redirect("/login/")
        else:
            # 'اطلاعات ورودی صحیح نیست!'
            msg = 'خطاهای فوق را رفع نمائید.'

    context = {
        "username": username,
        "access": access,
        "form": form,
        "msg": msg,
        "success": success
    }
    return render(request, "core/transfer-permissions.html", context)


@login_required(login_url="/login/")
def delete_directory_view(request, did, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    dir_ = Directory.objects.get(pk=did)
    bic = BankIdentifierCode.objects.get(code=dir_.bic.code)
    # bus = BusinessCode.objects.get(code=dir_.business.code)

    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus=dir_.business).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            try:
                if isc_user.role.code == 'ADMIN' or dir_.created_by.department == isc_user.department:
                    if dir_.parent == 0:
                        OperationBusiness.objects.filter(access_on_bus=dir_.business).delete()
                        bc = BusinessCode.objects.get(code=dir_.business.code)
                        bc.delete()
                        logger.warning(f'business and directory of {bc.code} has been deleted by {isc_user.user.username}.')
                    delete_dir_and_clean_sub_directories(dir_)
                    logger.info(f'directory in {dir_.absolute_path} with all of it\'s children and permissions of them has been deleted by {isc_user.user.username}.')
                    response = {'result': 'success', 'deleted_dir': did}
                else:
                    response = {'result': 'failed'}
            except Exception as e:
                logger.error(e)
                response = {'result': 'error'}
            
            return JsonResponse(data=response, safe=False)


