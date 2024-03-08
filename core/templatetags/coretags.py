from django import template
from django.db.models import QuerySet


register = template.Library()


@register.filter(name='item', is_safe=True)
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def remove_dot(string):
    return string.replace('.', '')


@register.filter
def replace_slash(obj, replace_with=' -> '):
    return str(obj).replace('/', replace_with)


@register.filter
def filter_invoices(invoices, status='UNDEFINED'):
    return invoices.filter(confirm_or_reject=status)


@register.filter
def add_invoices(invoices, new_list):
    final_list = []
    for item in invoices:
        final_list.append(item)
    for item in new_list:
        final_list.append(item)
    return final_list


@register.filter
def get_businesses(buss):
    buss_str = 'سامانه های'
    if buss.count() > 1:
        for bus in buss:
            bus_str = str(bus)
            buss_str += f' {bus_str.replace("سامانه ", "")}،'
        return buss_str[:-1]
    else:
        return buss.first()


@register.filter
def get_business_ids(buss):
    bus_ids = ''
    for bus in buss:
        bus_ids += f'{bus.id},'
    return bus_ids[:-1]


@register.filter
def clean_setad_business(bus):
    return bus.replace("SETAD_", "")


@register.filter
def get_organization_ids(orgs):
    org_ids = ''
    for org in orgs:
        org_ids += f'{org.id},'
    return org_ids[:-1]

