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