from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse, FileResponse
from django.template.loader import render_to_string

from core.models import IscUser, MftUser, Directory, Permission, DirectoryPermissionCode, BusinessCode, CustomerBank, OperationBusiness

from jdatetime import datetime as jdt

from mftusers.utils import make_form_from_invoice, export_user_with_paths, confirm_directory_tree

from .models import *

import logging

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def invoice_create_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    invoice = None
    invoice_type = None
    mftuser = None

    if request.is_ajax():
        if request.method == 'POST':
            try:
                invoice_type = InvoiceType.objects.get(code=request.POST.get('type'))
                if invoice_type.code == 'INVDIR':
                    # dirs = Directory.objects.filter(created_by=isc_user, is_confirmed=False).values('id')
                    dirs_str = request.POST.get('dirs')
                    # for d in dirs:
                    #     dirs_str += f'{str(d["id"])},'
                    invoice = PreInvoice(
                        invoice_type=invoice_type,
                        directories_list=dirs_str,
                        created_by=isc_user
                    )
                    invoice.save()
                else:
                    mftuser = MftUser.objects.get(pk=request.POST.get('mftuser'))
                    bus_dirs = []
                    perms_str = ''
                    if invoice_type.code == 'INVUBUS':
                        bus_dirs = Directory.objects.filter(business=BusinessCode.objects.get(pk=int(request.POST.get('ubus')))).order_by('relative_path')
                    elif invoice_type.code == 'INVOBUS':
                        bus_dirs = Directory.objects.filter(business__in=mftuser.business.all()).order_by('relative_path')
                    permissions = Permission.objects.filter(user=mftuser, directory__in=bus_dirs, is_confirmed=False)
                    if permissions.filter(permission__in=[1, 2, 32, 4]).exists():
                        for p in permissions.values('id').distinct():
                            perms_str += f'{p["id"]},'
                        invoice = Invoice(
                            invoice_type=invoice_type,
                            mftuser=mftuser.id,
                            used_business=int(request.POST.get('ubus')) if invoice_type.code == 'INVUBUS' else 0,
                            permissions_list=perms_str,
                            created_by=isc_user
                        )
                        invoice.save()
                        logger.info(f'invoice with serial number {invoice.serial_number} generated by {isc_user.user.username}.')
                        response = {
                            'result': 'success',
                            'invoice_id': invoice.id
                        }
                    else:
                        response = {
                            'result': 'error',
                            'message': 'برای ایجاد درخواست چارگون، باید حداقل یک دسترسی ایجاد کنید.'
                        }
                
            except Exception as e:
                logger.info(f'creating invoice encountered error.')
                logger.error(e)
                status_code = 400
                response = {
                    'result': 'error',
                    'message': 'خطایی رخ داده است، با مدیر سیستم تماس بگیرید.'
                }
            finally:
                return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def invoice_confirm_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice_type = InvoiceType.objects.get(code=request.POST.get('itype'))
            if invoice_type.code == 'INVDIR':
                invoice = PreInvoice.objects.get(pk=iid)
                if invoice.created_by == isc_user or isc_user.role.code == 'ADMIN':
                    dirs_list = [int(d) for d in invoice.directories_list.split(',')[:-1]]
                    Directory.objects.filter(pk__in=dirs_list).update(is_confirmed=True)
                    confirm_directory_tree(dirs_list, survey='BACKWARD')
                    invoice.confirm_or_reject = 'CONFIRMED'
                    invoice.save()
                    response = {
                        'result': 'success',
                        'type': 'pre',
                        'confirmed': invoice.id
                    }
                    logger.info(f'invoice with serial number {invoice.serial_number} confirmed by {isc_user.user.username}.')
                else:
                    logger.critical(f'unauthorized trying confirm of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.')
                    response = {
                        'result': 'error',
                        'message': 'شما مجاز به انجام این کار نیستید'
                    }
            else:
                invoice = Invoice.objects.get(pk=iid)
                if invoice.created_by == isc_user or isc_user.role.code == 'ADMIN':
                    mftuser = MftUser.objects.get(pk=invoice.mftuser)
                    mftuser.is_confirmed = True
                    mftuser.save()
                    perms_list = [int(p) for p in invoice.permissions_list.split(',')[:-1]]
                    Permission.objects.filter(pk__in=perms_list).update(is_confirmed=True)
                    export_user_with_paths(invoice.mftuser, isc_user)
                    invoice.confirm_or_reject = 'CONFIRMED'
                    invoice.save()
                    response = {
                        'result': 'success',
                        'type': '',
                        'confirmed': invoice.id
                    }
                    logger.info(f'invoice with serial number {invoice.serial_number} confirmed by {isc_user.user.username}.')
                else:
                    logger.critical(f'unauthorized trying confirm of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.')
                    response = {
                        'result': 'error',
                        'message': 'شما مجاز به انجام این کار نیستید'
                    }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def invoice_reject_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice_type = InvoiceType.objects.get(code=request.POST.get('itype'))
            if invoice_type.code == 'INVDIR':
                invoice = PreInvoice.objects.get(pk=iid)
            else:
                invoice = Invoice.objects.get(pk=iid)
            if invoice.created_by == isc_user or isc_user.role.code == 'ADMIN':
                invoice.confirm_or_reject = 'REJECTED'
                invoice.description = request.POST.get('reason')
                invoice.save()
                response = {
                    'result': 'success',
                    'type': 'pre' if invoice_type.code == 'INVDIR' else '',
                    'rejected': invoice.id
                }
                logger.info(f'invoice with serial number {invoice.serial_number} rejected by {isc_user.user.username}.')
            else:
                logger.critical(f'unauthorized trying reject of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.')
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def invoice_update_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice_type = InvoiceType.objects.get(code=request.POST.get('itype'))
            if invoice_type.code != 'INVDIR':
                # invoice = PreInvoice.objects.get(pk=iid)
                # else:
                invoice = Invoice.objects.get(pk=iid)
            if isc_user.role.code == 'ADMIN':
                invoice.confirm_or_reject = 'UNDEFINED'
                response = {
                    'result': 'success',
                    'type': 'pre' if invoice_type.code == 'INVDIR' else '',
                    'updated': invoice.id
                }
                invoice.save()
                logger.info(f'invoice with serial number {invoice.serial_number} updated by {isc_user.user.username}.')
            else:
                logger.critical(f'unauthorized trying update of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.')
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def invoice_delete_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice_type = InvoiceType.objects.get(code=request.POST.get('itype'))
            if invoice_type.code == 'INVDIR':
                invoice = PreInvoice.objects.get(pk=iid)
            else:
                invoice = Invoice.objects.get(pk=iid)
            if invoice.created_by == isc_user or isc_user.role.code == 'ADMIN':
                response = {
                    'result': 'success',
                    'type': 'pre' if invoice_type.code == 'INVDIR' else '',
                    'deleted': invoice.id
                }
                invoice.delete()
                logger.info(f'invoice with serial number {invoice.serial_number} deleted by {isc_user.user.username}.')
            else:
                logger.critical(f'unauthorized trying delete of invoice with serial number {invoice.serial_number} by {isc_user.user.username}.')
                response = {
                    'result': 'error',
                    'message': 'شما مجاز به انجام این کار نیستید'
                }
            return JsonResponse(data=response, safe=False)


@login_required(login_url='/login/')
def invoice_details_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    invoice = get_object_or_404(Invoice, pk=iid)
    mftuser = MftUser.objects.get(pk=invoice.mftuser)
    ubus = invoice.get_used_business()
    # bus_dirs = []
    # user_accesses = []

    if not isc_user.user.is_staff and not OperationBusiness.objects.filter(user=isc_user, access_on_bus__in=mftuser.business.all()).exists():
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            response = FileResponse(open(make_form_from_invoice(invoice, request.POST.get('contents')), 'rb'), as_attachment=True)
            response['Content-Disposition'] = f"attachment; filename={invoice.get_mftuser().username}.pdf"
            response['Content-Type'] = "file/pdf"
            logger.info(f'invoice with serial number {invoice.serial_number} downloaded by {isc_user.user.username}.')
            return response

    # if ubus:
    #     bus_dirs = Directory.objects.filter(business=ubus).order_by('relative_path')
    # else:
    #     bus_dirs = Directory.objects.filter(business__in=mftuser.business.all()).order_by('relative_path')
    
    # permissions = Permission.objects.filter(user=mftuser, directory__in=bus_dirs, permission__in=[1, 2, 32, 4], is_confirmed=False).order_by('directory__relative_path')
    
    # directory_ids = [p['directory'] for p in permissions.values('directory').distinct()]
    # for dir_ in Directory.objects.filter(id__in=directory_ids):
    #     perms = permissions.filter(directory=dir_)
    #     perms_str = ''
    #     for p in perms:
    #         perms_str += f'{DirectoryPermissionCode.objects.get(value=p.permission)}، '
    #     user_accesses.append({'dir': dir_.relative_path, 'perms': perms_str[:-2]})

    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'invoice': invoice,
        'jdate': jdt.now().strftime('%Y/%m/%d'),
        'counter': Invoice.objects.filter(mftuser=mftuser.id).count(),
        'ubus': ubus
        # 'user_accesses': invoice.get_list_of_permissions()
    }
    
    return render(request, 'invoice/invoice-details.html', context)


@login_required(login_url="/login/")
def invoices_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    invoices = []
    pre_invoices = []

    if str(isc_user.role.code) == 'ADMIN':
        invoices = Invoice.objects.all().order_by('created_at')
        pre_invoices = PreInvoice.objects.all().order_by('created_at')
    else:
        invoices = Invoice.objects.filter(created_by=isc_user).order_by('created_at')
        pre_invoices = PreInvoice.objects.filter(created_by=isc_user).order_by('created_at')

    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'invoices': invoices,
        'pre_invoices': pre_invoices
    }
    
    if request.is_ajax():
        if request.method == 'GET':
            query = request.GET.get('q')
            filtered_invoices = list(invoice for invoice in context['invoices'] if query in invoice.get_mftuser.username or query in invoice.get_mftuser.alias or query in invoice.get_mftuser.organization.description) # or query in user.business.description
            context['users'] = filtered_invoices
            html = render_to_string(
                template_name="includes/invoice-list.html", context=context
            )
            data_dict = {"html_from_view": html}
            return JsonResponse(data=data_dict, safe=False)
    
    return render(request, "invoice/invoices-list.html", context)

