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

from .models import *
from .forms import *

import logging

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def index_view(request):
    # buck insertion into or correction in db
    # insert_into_db()
    # clean_up(flag='dir', action=True)
    # clean_up(flag='perm2', action=True)
    # clean_up(flag='dir3', action=False, bic_name="FIU")

    isc_user = IscUser.objects.get(user=request.user)

    # users_count = len(MftUser.objects.all())
    # directories_count = len(Directory.objects.all())
    # banks_count = len(BankIdentifierCode.objects.all()) - 1

    context = {
        'segment': 'index',
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code)
        # 'users_count': str(users_count),
        # 'directories_count': str(directories_count),
        # 'banks_count': str(banks_count)
    }
    
    html_template = loader.get_template('core/index.html')
    return HttpResponse(html_template.render(context, request))


def register_user_view(request):
    msg = None
    success = False
    form = IscUserForm(request.POST or None)
    form.fields['department'].choices = [(dept.id, dept) for dept in IscDepartmentCode.objects.all().order_by('description')]
    form.fields['business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.all().order_by('description')]

    if request.method == "POST":
        # form = SignUpForm(request.POST)
        if form.is_valid():
            user = User(
                first_name=form.cleaned_data.get("firstname"),
                last_name=form.cleaned_data.get("lastname"),
                username=form.cleaned_data.get("username"),
                email=form.cleaned_data.get("email"),
                password=make_password(password=form.cleaned_data.get("password")),
                is_superuser=False,
                is_staff=False,
                is_active=False
            )
            user.save()
            user_role = form.cleaned_data.get("department").access_type
            businesses = form.cleaned_data.get("business")
            isc_user = IscUser(
                user=user,
                role=user_role,
                department=form.cleaned_data.get("department"),
                officephone=form.cleaned_data.get("officephone"),
                mobilephone=form.cleaned_data.get("mobilephone")
            )
            isc_user.save()
            logger.info(f'{isc_user.user.username} registered successfully.')
            bus_msg = ''
            if user_role.code == 'OPERATION':
                for bus in businesses:
                    bus_code = BusinessCode.objects.get(id=int(bus))
                    opr_buss = OperationBusiness.objects.filter(access_on_bus=bus_code).values('user')
                    user_depts = IscUser.objects.filter(id__in=[obu['user'] for obu in opr_buss]).values('department') #.exclude(user=isc_user.user)
                    udl = [IscDepartmentCode.objects.get(code=ud['department']) for ud in user_depts]
                    if user_depts.count() == 0 or isc_user.department in udl:
                        OperationBusiness.objects.create(user=isc_user, access_on_bus=BusinessCode.objects.get(id=int(bus)))
                        logger.info(f'access on {bus_code.code} for {isc_user.user.username} has beeen given.')
                    else:
                        logger.warning(f'access on {bus_code.code} for {isc_user.user.username} has beeen given.')
                        bus_msg += f'دسترسی به سامانه/پروژه {bus_code.code} ایجاد نشد. متعلق به گروه دیگری می باشد.\n'
            # elif user_role.code == 'CUSTOMER':
            #     pass

            msg = f'<p>کاربری {user.username} ایجاد گردید،<br />برای فعالسازی آن لطفاً با 29985700 تماس بگیرید.</p><br ><p>{bus_msg}</p>'
            success = True

            # return redirect("/login/")

        else:
            # 'اطلاعات ورودی صحیح نیست!'
            msg = form.errors

    context = {
        "form": form,
        "msg": msg,
        "success": success
    }
    return render(request, "accounts/register.html", context)


def login_view(request, *args, **kwargs):
    form = LoginForm(request.POST or None)

    msg = None
    next_ = "/"

    if request.META.get('QUERY_STRING'):
        qs = request.META.get('QUERY_STRING')
        if 'next' in qs:
            next_ = qs.split('=')[-1]
            if next_[-1] != '/':
                next_ += '/'

    if request.method == "POST":
        # isc_user = get_object_or_404(IscUser, user=request.user)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                logger.info(f'{username} has logged in successfully.')
                return redirect(next_)
            else:
                msg = 'نام کاربری یا کلمه عبور اشتباه است'
                if User.objects.filter(username=username, is_active=False).exists():
                    msg = 'کاربر شما به دلیل تغییر در پروفایل غیرفعال می باشد<br />برای فعالسازی با مدیر سیستم تماس بگیرید'
        else:
            msg = 'خطایی رخ داده است!'

    return render(request, "accounts/login.html", {"form": form, "msg": msg})


def logout_view(request, *args, **kwargs):
    logger.info(f'{request.user.username} has logged out successfully.')
    logout(request)
    return redirect('/login/')


@login_required(login_url='/login/')
def change_password_view(request, *args, **kwargs):
    user = request.user
    msg = None
    success = None

    if request.method == "POST":
        form = ChangePasswordForm(request.POST)
        if user.check_password(form.data.get('old_password')):
            if len(form.data.get('new_password')) > 8:
                if form.data.get('new_password') == form.data.get('repeat_password'):
                    user.set_password(form.data.get('new_password'))
                    user.save()
                    login(request, user)
                    msg = "کلمه عبور با موفقیت تغییر یافت"
                    success = True
                    logger.info(f'{user.username} has changed his/her password.')
                    # return redirect('/')
                else:
                    msg = 'تکرار کلمه عبور جدید صحیح وارد نشده است'
            else:
                msg = 'تعداد کاراکتر کلمه عبور جدید کوتاه است'
        else:
            msg = 'کلمه عبور قبلی صحیح وارد نشده است'
    else:
        form = ChangePasswordForm()

    context = {
        "access"
        "form": form,
        "msg": msg,
        "success": success
    }

    return render(request, "accounts/change-password.html", context)


@login_required(login_url="/login/")
def profile_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    profile_msg = bus_msg = None
    owned_by_user = []
    used_by_user = []
    submit_error = False
    
    # if not isc_user.user.is_staff:
    #     logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
    #     return redirect('/error/401/')

    isc_user_dict = {
        "username": isc_user.user.username,
        "firstname": isc_user.user.first_name,
        "lastname": isc_user.user.last_name,
        "email": isc_user.user.email,
        "officephone": isc_user.officephone,
        "mobilephone": isc_user.mobilephone,
        "department": isc_user.department.description
    }
    profile_form = UserProfileForm(request=request, initial=isc_user_dict)
    business_form = BusinessSelectionForm()
    if isc_user.role.code == 'OPERATION':
        user_businesses = OperationBusiness.objects.filter(user=isc_user) # , owned_by_user=True .values('access_on_bus').distinct()
        o_buss = [bus for bus in user_businesses.filter(owned_by_user=True)]
        u_buss = [bus for bus in user_businesses.filter(owned_by_user=False)]
        owned_by_user = [ob.access_on_bus.code for ob in o_buss]
        used_by_user = [ub.access_on_bus.code for ub in u_buss]
        business_form.fields['used_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=owned_by_user).order_by('description')]
    elif isc_user.role.code == 'ADMIN' or isc_user.role.code == 'CUSTOMER':
        o_buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
        u_buss = [] # [bus for bus in BusinessCode.objects.all().order_by('description')]
    business_form.fields['owned_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=used_by_user).order_by('description')]
    
    if request.method == 'POST':
        if request.POST.get("form-type") == "profile-form": # update iscuser (profile)
            profile_form = UserProfileForm(request.POST, request=request)
            if profile_form.is_valid():
                user = User.objects.get(username=isc_user.user.username)
                iscuser = IscUser.objects.get(user=user)
                user.username = profile_form.cleaned_data['username']
                user.email = profile_form.cleaned_data['email']
                user.first_name = profile_form.cleaned_data['firstname']
                user.last_name = profile_form.cleaned_data['lastname']
                user.is_active = False
                user.save()
                iscuser.mobilephone = profile_form.cleaned_data['mobilephone']
                iscuser.officephone = profile_form.cleaned_data['officephone']
                iscuser.save()
                logger.info(f'isc_user {user.username} edited his/her profile.')
                submit_error = False
                profile_msg = 'مشخصات شما بروزرسانی شد، برای تأیید تغییرات با مدیر سیستم تماس بگیرید.'
            else:
                submit_error = True
                profile_msg = profile_form.errors
        elif request.POST.get("form-type") == "business-form": # update iscuser list of projects (business)
            business_form = BusinessSelectionForm(request.POST)
            business_form.fields['owned_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=used_by_user).order_by('description')]
            business_form.fields['used_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=owned_by_user).order_by('description')]
            if business_form.is_valid():
                OperationBusiness.objects.filter(user=isc_user).delete()
                owned_businesses = business_form.cleaned_data.get("owned_business")
                used_businesses = business_form.cleaned_data.get("used_business")
                o_bus = [BusinessCode.objects.get(id=int(bus)) for bus in owned_businesses]
                u_bus = [BusinessCode.objects.get(id=int(bus)) for bus in used_businesses]
                for ob in o_bus:
                    OperationBusiness.objects.create(
                        user=isc_user,
                        access_on_bus=ob,
                        owned_by_user=True
                    )
                for ub in u_bus:
                    OperationBusiness.objects.create(
                        user=isc_user,
                        access_on_bus=ub,
                        owned_by_user=False
                    )
                user = User.objects.get(username=isc_user.user.username)
                user.is_active = False
                user.save()
                logger.info(f'isc_user {isc_user.user.username} edited his/her list of projects.')
                submit_error = False
                bus_msg = 'لیست پروژه های شما بروزرسانی شد. برای تأیید تغییرات با مدیر سیستم تماس بگیرید.'
            else:
                submit_error = True
                bus_msg = business_form.errors
                business_form.fields['owned_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=used_by_user).order_by('description')]
                business_form.fields['used_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=owned_by_user).order_by('description')]
    
    context = {
        'error': submit_error,
        'profile_msg': profile_msg,
        'bus_msg': bus_msg,
        'owned_business': [ob.access_on_bus for ob in o_buss] if isc_user.role.code == 'OPERATION' else [ob for ob in o_buss],
        'used_business': [ub.access_on_bus for ub in u_buss] if isc_user.role.code == 'OPERATION' else [],
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'profile_form': profile_form,
        'business_form': business_form
    }

    return render(request, "accounts/profile.html", context)


def error_view(request, err=None, *args, **kwargs):
    context = {}
    
    if err == 400 or err == None:
        html_template = loader.get_template('core/400.html')
        return HttpResponse(html_template.render(context, request))
    elif err == 401:
        html_template = loader.get_template('core/401.html')
        return HttpResponse(html_template.render(context, request))
    elif err == 404:
        html_template = loader.get_template('core/404.html')
        return HttpResponse(html_template.render(context, request))
    elif err == 500:
        html_template = loader.get_template('core/500.html')
        return HttpResponse(html_template.render(context, request))


@login_required(login_url="/login/")
def add_data_view(request, *args, **kwargs):
    msg = None
    success = False
    isc_user        = IscUser.objects.get(user=request.user)
    username        = str(isc_user.user.username)
    access          = str(isc_user.role.code)
    form = AddBusinessForm(request.POST or None)

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
def manage_data_view(request, uid=-1, *args, **kwargs):
    isc_user        = IscUser.objects.get(user=request.user)
    username        = str(isc_user.user.username)
    access          = str(isc_user.role.code)
    mftusers        = MftUser.objects.filter(is_confirmed=False).order_by('username')
    deleted_users   = MftUserTemp.objects.filter(description__icontains=f"%deleted%").order_by('username')
    # invoices        = Invoice.objects.filter(processed=False).order_by('created_at')
    invoices        = Invoice.objects.all().order_by('created_at')
    pre_invoices    = PreInvoice.objects.all().order_by('created_at')
    elements        = []
    new_users       = []
    changed_users   = []
    differences     = {}

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'GET':
            user = MftUser.objects.get(pk=uid)
            dirs = Permission.objects.filter(user=user).values('directory').distinct()
            # for perm in permissions:
            #     dict_dir = model_to_dict(perm.directory)
            #     dirs.append(dict_dir)
            # mftusers = [model_to_dict(perm.user) for perm in permissions]
            context = {
                'elements': get_dirs_with_changed_permissions(dirs, pretify=False),
                'filtered': True,
                'admin_view': True,
            }
            html = render_to_string(
                template_name="includes/directory-list.html", context=context
            )
            data_dict = {"html_from_view": html}
            return JsonResponse(data=data_dict, safe=False)

    for user in mftusers:
        if MftUserTemp.objects.filter(username=user.username).exists():
            changed_users.append(user)
            differences[user.username] = get_user_differences(
                MftUserTemp.objects.filter(username=user.username).first(),
                user
            )
        else:
            new_users.append(user)
    
    context = {
        'username': username,
        'admin_view': True,
        'access': access,
        'invoices': invoices,
        'pre_invoices': pre_invoices,
        'elements': get_users_with_changed_permissions(),
        'users': mftusers,
        'new_users': new_users,
        'deleted': deleted_users,
        'changed_users': changed_users,
        'differences': differences,
    }

    return render(request, "core/manage-data.html", context)


@login_required(login_url="/login/")
def export_data_view(request, *args, **kwargs):
    isc_user            = IscUser.objects.get(user=request.user)
    username            = str(isc_user.user.username)
    access              = str(isc_user.role.code)
    exported_mftusers   = ReadyToExport.objects.filter(is_downloaded=False)
    
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
            exported_user.is_downloaded = True
            exported_user.save()
            logger.info(f'mftuser {exported_user.mftuser.username} exported successfully.')
            response = {'result': 'success', 'deleted': exported_user.mftuser.username.replace('.', '')}
            return JsonResponse(data=response, safe=False)
        elif request.method == 'GET':
            query = request.GET.get('q')
            filtered_mftusers = list(user for user in context['exported'] if query in user.mftuser.username or query in user.mftuser.alias or query in user.mftuser.organization.description)
            context['exported'] = filtered_mftusers
            html = render_to_string(
                template_name="includes/users-list.html", context=context
            )
            data_dict = {"html_from_view": html}
            return JsonResponse(data=data_dict, safe=False)

    return render(request, "core/export-data.html", context)


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
        buss = [BusinessCode.objects.get(pk=bus.access_on_bus.id) for bus in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).order_by('access_on_bus')]
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
            for b in form.cleaned_data.get('business'):
                bus = BusinessCode.objects.get(id=int(b))
                if Directory.objects.filter(relative_path=f'{bus.code}/{mftuser.organization.directory_name}').exists():
                    mftuser.business.add(bus)
                    create_default_permission(
                        isc_user=isc_user,
                        mftuser=mftuser,
                        last_dir=Directory.objects.get(relative_path=f'{bus.code}/{mftuser.organization.directory_name}'),
                        business=bus,
                        home_dir=True
                    )
                    logger.info(f'access on business {bus.code} for {mftuser.username} has been created.')
                else:
                    bus_error += f'<p>اختصاص پروژه/سامانه {bus.code} میسر نیست.<p>'
                    logger.warning(f'access on business {bus.code} for {mftuser.username} has been not created.')
            
            if mftuser.organization.code == 'ISC':
                mftuser.description = str(isc_user.department)
            else:
                # buss = ''
                # for bus in mftuser.business.all():
                #     buss += f'{str(bus)}،'
                # project = "سامانه های" if mftuser.business.all().count() > 1 else "سامانه"
                # mftuser.description = f'کاربر {project} {buss[:-1]} {mftuser.organization}'
                mftuser.description = f'{mftuser.organization}'
            mftuser.save()
            msg = f'<p>کاربر {mftuser.username} ایجاد شد.<p><br >{bus_error}'
            success = True
        else:
            msg = form.errors
    
    context = {
        'crud': 'create',
        'form': form,
        'msg': msg,
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
        accesses = OperationBusiness.objects.filter(user=isc_user, owned_by_user=True)
        u_buss = [a.access_on_bus for a in accesses]
        mftusers = MftUser.objects.filter(business__in=u_buss).order_by('username').distinct()
    else:
        mftusers = MftUser.objects.all().order_by('username')

    context['users'] = mftusers
    # context['admin_view'] = True if isc_user.user.is_staff else False

    if request.is_ajax():
        # mftusers = MftUser.objects.filter(username__icontains=request.GET.get('q'))
        query = request.GET.get('q')
        filtered_mftusers = list(user for user in context['users'].order_by('username') if query in user.username or query in user.alias or query in user.organization.description) # or query in user.business.description
        context['users'] = filtered_mftusers
        html = render_to_string(
            template_name="includes/users-list.html", context=context
        )
        data_dict = {"html_from_view": html}
        return JsonResponse(data=data_dict, safe=False)

    # paginator = Paginator(non_paginated_users, paginate_by)
    # try:
    #     context['users'] = paginator.page(page)
    # except PageNotAnInteger:
    #     context['users'] = paginator.page(1)
    # except EmptyPage:
    #     context['users'] = paginator.page(paginator.num_pages)
    # context['is_paginated'] = True
    # context['page_obj'] = paginator.get_page(1)
    
    return render(request, "core/mftusers-list.html", context)


@login_required(login_url="/login/")
def mftuser_details_view(request, id, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=id)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    # bus = BusinessCode.objects.filter(code=mftuser.business.all())
    msg = None
    
    #  if mftuser.organization.code == '_ISC' else get_specific_root_dir(mftuser.organization.code)
    
    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=mftuser.business.all()).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if isc_user.role.code == 'CUSTOMER':
        orgs = [acc.access_on_bic for acc in CustomerBank.objects.filter(user=isc_user)]
        buss = [bus for bus in BusinessCode.objects.all()]
    elif isc_user.role.code == 'OPERATION':
        orgs = [acc for acc in BankIdentifierCode.objects.all()]
        buss = [bus.access_on_bus for bus in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True)]
    elif isc_user.role.code == 'ADMIN':
        orgs = [bic for bic in BankIdentifierCode.objects.all()]
        buss = [bus for bus in BusinessCode.objects.all()]
    
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
                # mftuser_temp.email=mftuser_origin.email,
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
            for bus in mftuser_origin.business.all():
                mftuser_temp.business.add(bus)
            dirs = [Directory.objects.get(relative_path=b.code) for b in mftuser_temp.business.all()]
            dirs_ = []
            for d in dirs:
                dirs_.append(d)
                dirs_.append(Directory.objects.get(relative_path=f'{d.business.code}/{mftuser_origin.organization.directory_name}'))
            Permission.objects.filter(directory__in=dirs_).delete()
            mftuser_origin.business.clear()
            for b in form.cleaned_data.get('business'):
                bus = BusinessCode.objects.get(id=int(b))
                if Directory.objects.filter(relative_path=f'{bus.code}/{mftuser_origin.organization.directory_name}').exists():
                    mftuser_origin.business.add(bus)
                    create_default_permission(
                        isc_user=isc_user,
                        mftuser=mftuser_origin,
                        last_dir=Directory.objects.get(relative_path=f'{bus.code}/{mftuser_origin.organization.directory_name}'),
                        business=bus,
                        home_dir=True
                    )
                    mftuser_origin.is_confirmed=False
                    mftuser_origin.description=mftuser.description
                    mftuser_origin.officephone=mftuser.officephone
                    mftuser_origin.mobilephone=mftuser.mobilephone
                    mftuser_origin.alias=mftuser.alias
                    mftuser_origin.ipaddr=mftuser.ipaddr
                    # mftuser_origin.disk_quota=mftuser.disk_quota
                    mftuser_origin.modified_at=timezone.now()
                    mftuser_origin.save()
                    msg = '<strong>اطلاعات کاربر بروزرسانی شد</strong>'
                    success = True
                else:
                    mftuser_origin.description=mftuser_temp.description
                    mftuser_origin.officephone=mftuser_temp.officephone
                    mftuser_origin.mobilephone=mftuser_temp.mobilephone
                    mftuser_origin.alias=mftuser_temp.alias
                    mftuser_origin.ipaddr=mftuser_temp.ipaddr
                    # mftuser_origin.disk_quota=mftuser_temp.disk_quota
                    mftuser_origin.modified_at=mftuser_temp.modified_at
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
        'confirmed': confirmed,
        'form': form
    }

    return render(request, "core/mftuser-details.html", context)


@login_required(login_url="/login/")
def mftuser_access_view(request, uid, pid=-1, dir_name="", *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    mftuser = get_object_or_404(MftUser, pk=uid)
    bic = BankIdentifierCode.objects.get(code=mftuser.organization.code)
    # bus = BusinessCode.objects.get(code=mftuser.business.code)
    # buss = mftuser.business.all()
    owned_buss = [ob.access_on_bus for ob in OperationBusiness.objects.filter(user=isc_user, owned_by_user=True).order_by('access_on_bus')]
    elements = None
    used_buss = None
    
    if not isc_user.user.is_staff and not CustomerBank.objects.filter(user=isc_user, access_on_bic=bic).exists() and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=owned_buss).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if isc_user.role.code == 'ADMIN':
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
    
    if request.is_ajax():
        if request.method == 'POST':
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
                logger.info(f'directory {new_dir.absolute_path} by {isc_user.user.username} has been created.')
                parent.children = f'{parent.children}{new_dir.id},'
                parent.save()
                # CustomerAccess.objects.create(
                #     user=isc_user,
                #     access_on=CustomerAccessCode.objects.get(code='Directory'),
                #     target_id=new_dir.id,
                #     access_type=CustomerAccessType.objects.get(code='MODIFIER'),
                #     created_at=timezone.now()
                # )
                create_default_permission(
                    isc_user=isc_user,
                    mftuser=mftuser,
                    last_dir=new_dir
                )
                # check_parents_permission(
                #     isc_user=isc_user,
                #     mftuser=mftuser,
                #     parent=new_dir.parent
                # )
                # data = {'id': new_dir.id, 'business': 'Name': new_dir.name, 'path': new_dir.relative_path}
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
            #TODO: correct js events
            query = request.GET.get('q')
            if query != '':
                context['elements'] = get_all_dirs(isc_user, query, False)
                filtered_elements = list(el for el in context['elements'] if query in el.get('dir').name)
                context['elements'] = filtered_elements
                context['filtered'] = True
                html = render_to_string(
                    template_name="includes/directory-list.html", context=context
                )
            else:
                html = ""
            data_dict = {"html_from_view": html}
            return JsonResponse(data=data_dict, safe=False)

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
                # mftuser.email = mftuser_orig.email
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
        if request.method == 'POST':
            old_permissions = []
            splited = []
            status_code = 200
            response = {}
            try:
                permissions = request.POST.get('permissions')
                splited = [int(t) for t in permissions.split(',')[:-1]]
                old_permissions = [ae for ae in Permission.objects.filter(user=mftuser, directory=directory)]
                for op in old_permissions:
                    if op.permission not in splited:
                        if isc_user.role.code != 'ADMIN':
                            if op.permission == 1: #Download (Read)
                                Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete()   #Checksum
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete() #List
                                splited.remove(128)
                            elif op.permission == 2: #Upload (Write)
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete() #Checksum
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete() #List
                                Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()   #Overwrite
                                Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                                splited.remove(512)
                                splited.remove(1024)
                            elif op.permission == 32: #Delete (Modify)
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=1).delete()    #Download
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=2).delete()    #Upload
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=128).delete()  #Checksum
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=256).delete()  #List
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()  #Overwrite
                                # Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete() #Append
                                Permission.objects.filter(user=mftuser, directory=directory, permission=8).delete()      #Rename
                                splited.remove(8)
                        op.delete()
                for pv in splited:
                    perm = DirectoryPermissionCode.objects.get(value=pv)
                    if not Permission.objects.filter(user=mftuser, directory=directory, permission=perm.value).exists():
                        perm = Permission(
                            user=mftuser,
                            directory=directory,
                            permission=perm.value,
                            created_by=isc_user
                        )
                        perm.save()
                        check_parents_permission(
                            isc_user=isc_user,
                            mftuser=mftuser,
                            parent=directory.parent
                            # permission=perm.value,
                        )
                    if pv == 1: #Download (Read)
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
                    # elif pv == 0: #Subdirectory (ایجاد پوشه)
                    #     reduce_parents_permission()
                logger.info(f'permission of directory {directory.absolute_path} for mftuser {mftuser.username} changed to {splited} by {isc_user.user.username}.')
                response = {'result': 'success'}
            except Exception as e:
                print(e)
                status_code = 400
                logger.error(f'permission change on directory {directory.absolute_path} to {splited} by {isc_user.user.username} encountered with error.')
                response = {'result': 'error', 'perms': [str(op) + "," for op in old_permissions]}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)
        elif request.method == 'GET':
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
            old_permissions = []
            splited = []
            status_code = 200
            response = {}
            try:
                permissions = request.POST.get('permissions')
                splited = [int(t) for t in permissions.split(',')[:-1]]
                action = request.POST.get('action')
                if action == 'remove':
                    for pv in splited:
                        if Permission.objects.filter(user=mftuser, directory=directory, permission=pv).exists():
                            Permission.objects.filter(user=mftuser, directory=directory, permission=pv).delete()
                        if pv == 1: #Download (Read)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                        elif pv == 2: #Upload (Write)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=512).delete()   #Overwrite
                            Permission.objects.filter(user=mftuser, directory=directory, permission=1024).delete()  #Append
                        elif pv == 32: #Delete (Modify)
                            Permission.objects.filter(user=mftuser, directory=directory, permission=8).delete()      #Rename
                elif action == 'add':
                    for pv in splited:
                        if not Permission.objects.filter(user=mftuser, directory=directory, permission=pv).exists():
                            perm = Permission(
                                user=mftuser,
                                directory=directory,
                                permission=pv,
                                created_by=isc_user
                            )
                            perm.save()
                            check_parents_permission(
                                isc_user=isc_user,
                                mftuser=mftuser,
                                parent=directory.parent
                                # permission=perm.value,
                            )
                        if pv == 1: #Download (Read)
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
                print(e)
                status_code = 400
                logger.error(f'permission change on directory {directory.absolute_path} to {splited} by {isc_user.user.username} encountered with error.')
                response = {'result': 'error'}
            finally:
                return JsonResponse(data=response, safe=False, status=status_code)


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
                if isc_user.role.code == 'ADMIN' or dir_.created_by.pk == isc_user.pk:
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
                print(e)
                response = {'result': 'error'}
            
            return JsonResponse(data=response, safe=False)


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

