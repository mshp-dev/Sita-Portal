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


def index_view(request):
    context = {
        'users_count': MftUser.objects.all().count(),
        'directories_count': Directory.objects.all().count(),
        'business_count': BusinessCode.objects.all().count(),
        'organizations_count': BankIdentifierCode.objects.all().count()
    }
    
    html_template = loader.get_template('core/index.html')
    return HttpResponse(html_template.render(context, request))


def register_user_view(request):
    msg = None
    success = False
    access_type = 'CUSTOMER'
    form = IscUserForm(request.POST or None)

    if request.is_ajax():
        if request.method == "GET":
            try:
                dept_id = request.GET.get('dept')
                department = IscDepartmentCode.objects.get(pk=int(dept_id))
                response = {
                    "result": "success",
                    "type": department.access_type.code
                }
            except Exception as e:
                print(e)
                logger.info(f'{e}.')
                response = {
                    "result": "error",
                    "message": "مشکلی پیش آمده است، با مدیر سیستم تماس بگیرید."
                }
        return JsonResponse(data=response, safe=False)
    
    form.fields['department'].choices = [(dept.id, dept) for dept in IscDepartmentCode.objects.all().order_by('description')]
    form.fields['business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.all().order_by('description')]
    form.fields['organization'].choices = [(org.id, org) for org in BankIdentifierCode.objects.all().order_by('description')]

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
            organizations = form.cleaned_data.get("organization")
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
            elif user_role.code == 'CUSTOMER':
                for org in organizations:
                    organization = BankIdentifierCode.objects.get(id=int(org))
                    CustomerBank.objects.create(
                        user=isc_user,
                        access_on_bic=organization
                    )
                    logger.info(f'access on {organization.code} for {isc_user.user.username} has beeen given.')
            msg = f'<p>کاربری {user.username} ایجاد گردید،<br />برای فعالسازی آن لطفاً با 29985700 تماس بگیرید.</p><br ><p>{bus_msg}</p>'
            success = True
            # return redirect("/login/")
        else:
            # 'اطلاعات ورودی صحیح نیست!'
            msg = form.errors
            access_type = form.cleaned_data.get("department").access_type.code

    context = {
        "form": form,
        "msg": msg,
        "success": success,
        "access_type": access_type
    }
    return render(request, "accounts/register.html", context)


def login_view(request, *args, **kwargs):
    form = LoginForm(request.POST or None)

    msg = None
    next_ = "/dashboard/"

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
    return redirect('/')


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


@login_required(login_url='/login/')
def dashboard_view(request):
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

    isc_user = IscUser.objects.get(user=request.user)

    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code)
    }
    
    html_template = loader.get_template('core/dashboard.html')
    return HttpResponse(html_template.render(context, request))


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
        "form": form,
        "msg": msg,
        "success": success
    }

    return render(request, "accounts/change-password.html", context)


@login_required(login_url="/login/")
def profile_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    profile_msg = bus_msg = org_msg = None
    owned_by_user = []
    used_by_user = []
    user_orgs = []
    o_buss = []
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
    organization_form = OrganizationSelectionForm()
    if isc_user.role.code == 'OPERATION':
        user_businesses = OperationBusiness.objects.filter(user=isc_user) # , owned_by_user=True .values('access_on_bus').distinct()
        o_buss = [bus for bus in user_businesses.filter(owned_by_user=True)]
        u_buss = [bus for bus in user_businesses.filter(owned_by_user=False)]
        owned_by_user = [ob.access_on_bus.code for ob in o_buss]
        used_by_user = [ub.access_on_bus.code for ub in u_buss]
        business_form.fields['used_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=owned_by_user).order_by('description')]
    elif isc_user.role.code == 'CUSTOMER':
        user_organizations = CustomerBank.objects.filter(user=isc_user).order_by('access_on_bic__description')
        user_orgs = [org.access_on_bic for org in user_organizations]
    elif isc_user.role.code == 'ADMIN':
        o_buss = [bus for bus in BusinessCode.objects.all().order_by('description')]
        u_buss = [] # [bus for bus in BusinessCode.objects.all().order_by('description')]
        user_orgs = BankIdentifierCode.objects.all().order_by('description')
    business_form.fields['owned_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=used_by_user).order_by('description')]
    organization_form.fields['organizations'].choices = [(org.id, org) for org in BankIdentifierCode.objects.all().order_by('description')]
    
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
                bus_msg = 'لیست سامانه/پروژه های شما بروزرسانی شد. برای تأیید تغییرات با مدیر سیستم تماس بگیرید.'
            else:
                submit_error = True
                bus_msg = business_form.errors
                business_form.fields['owned_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=used_by_user).order_by('description')]
                business_form.fields['used_business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.exclude(code__in=owned_by_user).order_by('description')]
        elif request.POST.get("form-type") == "organization-form": # update iscuser list of organizations
            organization_form = OrganizationSelectionForm(request.POST)
            organization_form.fields['organizations'].choices = [(org.id, org) for org in BankIdentifierCode.objects.all().order_by('description')]
            if organization_form.is_valid():
                CustomerBank.objects.filter(user=isc_user).delete()
                selected_orgs = organization_form.cleaned_data.get("organizations")
                for bic in BankIdentifierCode.objects.filter(id__in=selected_orgs):
                    CustomerBank.objects.create(
                        user=isc_user,
                        access_on_bic=bic
                    )
                user = User.objects.get(username=isc_user.user.username)
                user.is_active = False
                user.save()
                logger.info(f'isc_user {isc_user.user.username} edited his/her list of bics.')
                submit_error = False
                org_msg = 'لیست سازمان/بانک های شما بروزرسانی شد. برای تأیید تغییرات با مدیر سیستم تماس بگیرید.'
            else:
                submit_error = True
                org_msg = organization_form.errors
                organization_form.fields['organizations'].choices = [(org.id, org) for org in BankIdentifierCode.objects.all().order_by('description')]

    context = {
        'error': submit_error,
        'profile_msg': profile_msg,
        'bus_msg': bus_msg,
        'org_msg': org_msg,
        'owned_business': [ob.access_on_bus for ob in o_buss] if isc_user.role.code == 'OPERATION' else [ob for ob in o_buss],
        'used_business': [ub.access_on_bus for ub in u_buss] if isc_user.role.code == 'OPERATION' else [],
        'organizations': user_orgs,
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'profile_form': profile_form,
        'business_form': business_form,
        'organization_form': organization_form
    }

    return render(request, "accounts/profile.html", context)


