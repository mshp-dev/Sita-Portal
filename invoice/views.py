from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse, FileResponse
from django.template.loader import render_to_string

from core.models import IscUser, MftUser, Directory, Permission, DirectoryPermissionCode, BusinessCode, CustomerBank, OperationBusiness
from mftusers.utils import make_form_from_invoice, export_user_with_paths_v2, confirm_directory_tree, check_directory_tree_permission, check_directories_minimum_permissions
from .models import *

from jdatetime import datetime as jdt
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
                    response = {
                        'result': 'success',
                        'invoice_id': invoice.id
                    }
                else:
                    mftuser = MftUser.objects.get(pk=request.POST.get('mftuser'))
                    bus_dirs = []
                    perms_str = ''
                    if invoice_type.code == 'INVUBUS':
                        bus_dirs = Directory.objects.filter(business=BusinessCode.objects.get(pk=int(request.POST.get('ubus')))).order_by('relative_path')
                    elif invoice_type.code == 'INVOBUS':
                        bus_dirs = Directory.objects.filter(business__in=mftuser.business.all()).order_by('relative_path')
                    # for bd in bus_dirs.filter(parent=0):
                    #     if not Permission.objects.filter(user=mftuser, directory=bd, permission=256).exists():
                    #         logger.warn(f'default permission on {bd.absolute_path} for {mftuser.username} does not exists.')
                    #         Permission.objects.create(
                    #             user=mftuser,
                    #             directory=bd,
                    #             permission=256, # List (مشاهده)
                    #             created_by=isc_user
                    #         )
                    #         logger.info(f'list permission on directory {bd.absolute_path} for mftuser {mftuser.username} created by {isc_user.user.username}.')
                    check_directories_minimum_permissions(isc_user, mftuser)
                    check_directory_tree_permission(isc_user, mftuser)
                    permissions = Permission.objects.filter(user=mftuser, directory__in=bus_dirs, is_confirmed=False)
                    if permissions.filter(permission__in=[1, 2, 32, 4]).exists():
                        for p in permissions.values('id').distinct():
                            perms_str += f'{p["id"]},'
                        invoice = Invoice(
                            invoice_type=invoice_type,
                            mftuser=mftuser,
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

    if not isc_user.user.is_staff:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            invoice = None
            invoice_type = InvoiceType.objects.get(code=request.POST.get('itype'))
            if invoice_type.code == 'INVDIR':
                invoice = PreInvoice.objects.get(pk=iid)
                if isc_user.role.code == 'ADMIN':
                    dirs_list = [int(d) for d in invoice.directories_list.split(',')[:-1]]
                    Directory.objects.filter(pk__in=dirs_list).update(is_confirmed=True)
                    confirm_directory_tree(dirs_list, survey='BACKWARD')
                    invoice.confirm_or_reject = 'CONFIRMED'
                    invoice.status = 1
                    # invoice.managed_by = isc_user
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
                if isc_user.role.code == 'ADMIN':
                    mftuser = MftUser.objects.get(pk=invoice.mftuser.id)
                    mftuser.is_confirmed = True
                    mftuser.modified_at = timezone.now()
                    if invoice_type.code == 'INVUNLS':
                        mftuser.set_max_sessions_unlimited()
                        mftuser.password_expiration_interval = invoice.used_business
                    else:
                        perms_list = [int(p) for p in invoice.permissions_list.split(',')[:-1]]
                        perms_list_exists = []
                        for p in perms_list:
                            if Permission.objects.filter(pk=p).exists():
                                perms_list_exists.append(p)
                            else:
                                logger.warn(f'permission with id {p} does not exists.')
                        Permission.objects.filter(pk__in=perms_list_exists).update(is_confirmed=True)
                    mftuser.save()
                    # export_user_with_paths(invoice.mftuser, isc_user)
                    export_user_with_paths_v2(invoice.mftuser, isc_user)
                    invoice.confirm_or_reject = 'CONFIRMED'
                    invoice.status = 1
                    # invoice.managed_by = isc_user
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
            if isc_user.role.code == 'ADMIN':
                invoice.confirm_or_reject = 'REJECTED'
                invoice.status = -1
                # invoice.managed_by = isc_user
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
                invoice.status = 0
                # invoice.managed_by = isc_user
                invoice.save()
                response = {
                    'result': 'success',
                    'type': 'pre' if invoice_type.code == 'INVDIR' else '',
                    'updated': invoice.id
                }
                logger.info(f'status of invoice with serial number {invoice.serial_number} updated to undefined by {isc_user.user.username}.')
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
    # mftuser = MftUser.objects.get(pk=invoice.mftuser)
    ubus = invoice.get_used_business()
    # bus_dirs = []
    # user_accesses = []

    if not isc_user.user.is_staff and not invoice.created_by == isc_user:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'POST':
            response = FileResponse(open(make_form_from_invoice(invoice, request.POST.get('contents')), 'rb'), as_attachment=True)
            response['Content-Disposition'] = f"attachment; filename={invoice.mftuser.username}.pdf"
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
        'counter': Invoice.objects.filter(mftuser=invoice.mftuser.id).count(),
        'ubus': ubus
        # 'user_accesses': invoice.get_list_of_permissions()
    }
    
    return render(request, 'invoice/invoice-details.html', context)


@login_required(login_url="/login/")
def invoices_list_view(request, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    invoices = []
    pre_invoices = []
    search_template_name = ""

    if str(isc_user.role.code) == 'ADMIN':
        invoices = Invoice.objects.all()
        pre_invoices = PreInvoice.objects.all()
        search_template_name = "includes/admin-invoice-list.html"
    else:
        invoices = Invoice.objects.filter(created_by=isc_user)
        pre_invoices = PreInvoice.objects.filter(created_by=isc_user)
        search_template_name = "includes/invoice-list.html"

    context = {
        'username': str(isc_user.user.username),
        'access': str(isc_user.role.code),
        'invoices': invoices.order_by('-created_at'),
        'pre_invoices': pre_invoices.order_by('-created_at')
    }
    
    if request.is_ajax():
        # if request.method == 'GET':
            # if request.GET.get('q') != '':
            #     field = request.GET.get('q').split(':')[0]
            #     query = request.GET.get('q').split(':')[-1]
            #     filtered_invoices = []
            #     filtered_pre_invoices = []
            #     if field == 'usr':
            #         for invoice in context['invoices']:
            #             if query in invoice.get_mftuser.username:
            #                 filtered_invoices.append(invoice)
            #     elif field == 'als':
            #         for invoice in context['invoices']:
            #             if query in invoice.get_mftuser.username:
            #                 filtered_invoices.append(invoice)
            #     elif field == 'org':
            #         for invoice in context['invoices']:
            #             if query in invoice.get_mftuser.organization.description:
            #                 filtered_invoices.append(invoice)
            #     elif field == 'sn':
            #         for invoice in context['invoices']:
            #             if query in invoice.serial_number:
            #                 filtered_invoices.append(invoice)
            #         for invoice in context['pre_invoices']:
            #             if query in invoice.serial_number:
            #                 filtered_pre_invoices.append(invoice)
            #     context['invoices'] = filtered_invoices
            #     context['pre_invoices'] = filtered_pre_invoices
            # html = render_to_string(
            #     template_name=search_template_name, context=context
            # )
            # data_dict = {"html_from_view": html}
            # return JsonResponse(data=data_dict, safe=False)
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
                    inv_serials = [str(q) for q in query.split(',')]
                    for inv in invoices:
                        if inv.serial_number in inv_serials:
                            filtered_invs['invoices'].append(int(inv.id))
                    for inv in pre_invoices:
                        if inv.serial_number in inv_serials:
                            filtered_invs['pre_invoices'].append(int(inv.id))
                else:
                    for inv in invoices:
                        # mftuser = inv.get_mftuser()
                        if query in inv.mftuser.username or query in inv.mftuser.alias or query in inv.mftuser.organization.description or query in inv.serial_number or query in inv.created_by.user.username or query in inv.get_jalali_created_at():
                            filtered_invs['invoices'].append(inv.id)
                    for inv in pre_invoices:
                        if query in inv.serial_number or query in inv.created_by.user.username or query in inv.get_jalali_created_at():
                            filtered_invs['pre_invoices'].append(inv.id)
            return JsonResponse(data={"filtered_invs": filtered_invs}, safe=False)
    
    return render(request, "invoice/invoices-list.html", context)


@login_required(login_url='/login/')
def invoice_get_permissions_view(request, iid, *args, **kwargs):
    isc_user = IscUser.objects.get(user=request.user)
    invoice = get_object_or_404(Invoice, pk=iid)
    
    if not isc_user.user.is_staff and not invoice.created_by == isc_user:
        logger.fatal(f'unauthorized trying access of {isc_user.user.username} to {request.path}.')
        return redirect('/error/401/')

    if request.is_ajax():
        if request.method == 'GET':
            try:
                permissions_list = 'دسترسی بر روی مسیرها:<br><br>'
                # f'<span class="display-6 text-tertiary mb-2">({inv_perm["perms"]}) بر روی {inv_perm["dir"]}</span><br>'
                for inv_perm in invoice.get_list_of_permissions():
                    permissions_list += \
                        f'''<div class="d-flex justify-content-between"> \
                            <span class="display-6 mb-2"> \
                                <strong class="text-success">({inv_perm["perms"]})</strong> بر روی\
                            </span> \
                            <span class="display-6 text-tertiary mb-2"> \
                                {inv_perm["dir"]} \
                            </span> \
                        </div>'''
                response = {
                    'result': 'success',
                    'invoice_id': invoice.id,
                    'permissions_list': permissions_list
                }
            except Exception as e:
                logger.error(e)
                response = {
                    'result': 'error',
                    'message': 'خطایی رخ داده است، با مدیر سیستم تماس بگیرید.'
                }
            finally:
                return JsonResponse(data=response, safe=False)

