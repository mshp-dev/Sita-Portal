from django.http.response import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import F

from mftusers.utils import export_setad_user_v2
from core.models import IscUser, IscDepartmentCode, BusinessCode
from invoice.models import InvoiceType

from .models import *
from .forms import *

from jdatetime import datetime as jdt

import logging

logger = logging.getLogger(__name__)


def setad_user_create_view(request, *args, **kwargs):
    msg = None
    success = False
    form = SetadUserForm(request.POST or None)

    form.fields['group_type'].choices = [(dept.id, dept) for dept in IscDepartmentCode.objects.filter(code__endswith='-SETAD').order_by('description')]
    form.fields['business'].choices = [(bus.id, bus) for bus in BusinessCode.objects.filter(code__startswith='SETAD_', code=F('description')).order_by('description')]
    
    if request.method == "POST":
        if form.is_valid():
            invoice = SetadUserInvoice(
                invoice_type=InvoiceType.objects.get(code='INVSTDU'),
                firstname=form.cleaned_data.get("firstname"),
                lastname=form.cleaned_data.get("lastname"),
                username=form.cleaned_data.get("username"),
                email=form.cleaned_data.get("email"),
                officephone=form.cleaned_data.get("officephone"),
                mobilephone=form.cleaned_data.get("mobilephone"),
                group_type=form.cleaned_data.get("group_type"),
                department=form.cleaned_data.get("department"),
                created_by=IscUser.objects.get(user__username='admin')
            )
            invoice.set_business(form.cleaned_data.get("business"))
            invoice.save()
            logger.info(f'an invoice for username {invoice.username} in setad generated successfully.', request)
            # create_permissions_for_setad_user(invoice)
            return redirect(f"/setad/invoice/details/{invoice.pk}/")
        else:
            # 'اطلاعات ورودی صحیح نیست!'
            logger.error(form.errors, request)
            msg = form.errors

    context = {
        "form": form,
        "buss": BusinessCode.objects.filter(code__startswith='SETAD_', code=F('description')).order_by('description'),
        "msg": msg,
        "success": success
    }
    return render(request, "setad/user-form.html", context)


def setad_user_invoice_view(request, iid, *args, **kwargs):
    invoice = get_object_or_404(SetadUserInvoice, pk=iid)
    context = {
        "invoice": invoice,
        'jdate': jdt.now().strftime('%Y/%m/%d'),
        'counter': SetadUserInvoice.objects.filter(username=invoice.username).count(),
    }
    logger.info(f'inquiry of invoice for setad user {invoice.username}', request)
    return render(request, "setad/user-invoice-details.html", context)


@login_required(login_url='/login/')
def setad_user_invoice_confirm_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            invoice = SetadUserInvoice.objects.get(pk=iid)
            if isc_user.role.code == 'ADMIN':
                AzmoonDirectoryPermission.objects.filter(invoice=invoice).update(is_confirmed=True)
                # export_setad_user(invoice, isc_user)
                export_setad_user_v2(invoice)
                invoice.confirm_or_reject = 'CONFIRMED'
                invoice.status = 1
                invoice.save()
                response = {
                    'result': 'success',
                    'confirmed': invoice.id
                }
                logger.info(f'setad user invoice with serial number {invoice.serial_number} confirmed by {isc_user.user.username}.', request)
            else:
                logger.critical(f'unauthorized trying confirm of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.', request)
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def setad_user_invoice_update_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            invoice = SetadUserInvoice.objects.get(pk=iid)
            if isc_user.role.code == 'ADMIN':
                invoice.confirm_or_reject = 'UNDEFINED'
                invoice.status = 0
                invoice.save()
                response = {
                    'result': 'success',
                    'confirmed': invoice.id
                }
                logger.info(f'setad user invoice with serial number {invoice.serial_number} changed to undefined by {isc_user.user.username}.', request)
            else:
                logger.critical(f'unauthorized trying confirm of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.', request)
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def setad_user_invoice_delete_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice = SetadUserInvoice.objects.get(pk=iid)
            if isc_user.role.code == 'ADMIN':
                response = {
                    'result': 'success',
                    'deleted': invoice.id
                }
                invoice.delete()
                logger.info(f'setad user invoice with serial number {invoice.serial_number} deleted by {isc_user.user.username}.', request)
            else:
                logger.critical(f'unauthorized trying delete of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.', request)
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url="/login/")
def manage_setad_user_invoice_view(request, uid=-1, *args, **kwargs):
    isc_user        = IscUser.objects.get(user=request.user)
    username        = str(isc_user.user.username)
    access          = str(isc_user.role.code)
    invoices        = SetadUserInvoice.objects.all().order_by('-created_at')

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.', request)
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'GET':
            query = request.GET.get('q')
            filtered_invs = {
                'invoices': [inv.id for inv in invoices]
            }
            if query != '':
                filtered_invs = {
                    'invoices': []
                }
                if ',' in query:
                    for inv in query.split(','):
                        filtered_invs['invoices'].append(int(inv))
                else:
                    for inv in invoices:
                        if query in inv.username or query in inv.firstname or query in inv.lastname or query in inv.serial_number or query in inv.department or query in inv.get_jalali_created_at() or query in inv.business:
                            filtered_invs['invoices'].append(inv.id)
            return JsonResponse(data={"filtered_invs": filtered_invs}, safe=False)

    context = {
        'username': username,
        'admin_view': True,
        'access': access,
        'invoices': invoices
    }

    return render(request, "setad/manage-invoices.html", context)
