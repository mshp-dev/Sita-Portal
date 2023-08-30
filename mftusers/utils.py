from django.contrib.auth.models import User
from django.core.files import File
from django.conf import settings
from django.db.models import Sum, Q
from pathlib import Path

from core.models import *
from invoice.models import *

from tempfile import NamedTemporaryFile as ntf
from lxml import etree as ET
from lxml import html
import os, random, zipfile, csv, pdfkit, sys, paramiko

from jdatetime import datetime as jdt

import logging

logger = logging.getLogger(__name__)


def get_not_confirmed_dirs(dirs):
    all_dirs = []
    ids = [d['directory'] for d in ids_dict]
    if pretify:
        dirs = Directory.objects.filter(id__in=ids, parent=parent).order_by('relative_path')
        return [{'dir': d, 'children': get_dirs_with_changed_permissions(ids_dict, parent=d.id)} for d in dirs]
    else:
        return [{'dir': d, 'children': []} for d in Directory.objects.filter(id__in=ids).order_by('relative_path')]


def get_specific_root_dir(buss, bic):
    root_dirs = Directory.objects.filter(parent=0, business__in=buss).order_by('name')
    if bic.code == 'ISC':
        all_dirs = []
        for rd in root_dirs:
            bank_dirs = Directory.objects.filter(parent=rd.id, is_confirmed=True).order_by('name') # business=rd.business, 
            all_dirs.append({'dir': rd, 'children': [{'dir': b, 'children': get_sub_dirs(b)} for b in bank_dirs]})
            # [{'dir': Directory.objects.get(bic=bic, parent=rd.id), 'children': get_sub_dirs(Directory.objects.get(bic=bic, parent=rd.id))}]})
        return all_dirs
    else:
        return [{'dir': rd, 'children': [{'dir': Directory.objects.get(bic=bic, parent=rd.id), 'children': get_sub_dirs(Directory.objects.get(bic=bic, parent=rd.id))}]} for rd in root_dirs]


def get_all_dirs(isc_user, owned=True, query=None, pretify=True):
    if str(isc_user.role.code) == 'CUSTOMER':
        accesses = CustomerBank.objects.filter(user=isc_user).order_by('access_on_bic')
        d_bics = [a.access_on_bic for a in accesses]
        if query:
            all_dirs = Directory.objects.all().order_by('name')
            root_dirs = all_dirs.filter(relative_path__icontains=query, bic__in=d_bics).order_by('name')
        else:
            root_dirs = Directory.objects.filter(parent=0).order_by('name')
            return [{'dir': d, 'children': [{'dir': b, 'children': get_sub_dirs(b, query, dir_create_view=True)} for b in (Directory.objects.filter(parent=d.id, bic__in=d_bics).order_by('name') if pretify else Directory.objects.filter(bic__in=d_bics).order_by('name'))]} for d in root_dirs]
    elif str(isc_user.role.code) == 'OPERATION':
        accesses = OperationBusiness.objects.filter(user=isc_user, owned_by_user=owned).order_by('access_on_bus')
        d_buss = [a.access_on_bus for a in accesses]
        if query:
            all_dirs = Directory.objects.all().order_by('name')
            root_dirs = all_dirs.filter(relative_path__icontains=query, business__in=d_buss).order_by('name')
        else:
            root_dirs = Directory.objects.filter(parent=0, business__in=d_buss).order_by('name') if pretify else Directory.objects.filter(business__in=d_buss).order_by('name')
    else:
        if query:
            all_dirs = Directory.objects.all().order_by('name')
            root_dirs = all_dirs.filter(relative_path__icontains=query).order_by('name')
        else:
            root_dirs = Directory.objects.filter(parent=0).order_by('name')
        
    return [{'dir': d, 'children': get_sub_dirs(d, query, dir_create_view=True) if pretify else []} for d in root_dirs]


def get_dirs_with_changed_permissions(ids_dict, pretify=True):
    parent = 0
    ids = [d['directory'] for d in ids_dict]
    if pretify:
        dirs = Directory.objects.filter(id__in=ids, parent=parent).order_by('relative_path')
        return [{'dir': d, 'children': get_dirs_with_changed_permissions(ids_dict, parent=d.id)} for d in dirs]
    else:
        return [{'dir': d, 'children': []} for d in Directory.objects.filter(id__in=ids).order_by('relative_path')]


def get_users_with_changed_permissions():
    changed_permissions = Permission.objects.filter(is_confirmed=False).values('user').distinct()
    users_ids = [cp['user'] for cp in changed_permissions]
    mftusers = MftUser.objects.filter(id__in=users_ids)
    return mftusers


def get_sub_dirs(dir_, q=None, dir_create_view=False):
    temp = dir_.children.split(',')[:-1]
    children = []
    if len(temp) > 0:
        chs = [int(t) for t in temp]
        chs.sort()
        for id_ in chs:
            try:
                d = Directory.objects.get(pk=id_)
                if dir_create_view:
                    if q:
                        if d.name.contains(q):
                            children.append({'dir': d, 'children': get_sub_dirs(d, q, dir_create_view=True)})
                    else:
                        children.append({'dir': d, 'children': get_sub_dirs(d, dir_create_view=True)})
                elif d.is_confirmed:
                    if q:
                        if d.name.contains(q):
                            children.append({'dir': d, 'children': get_sub_dirs(d, q)})
                    else:
                        children.append({'dir': d, 'children': get_sub_dirs(d)})
            except:
                logger.error(f'directory with id {id_} does not exists, parent id is {dir_.parent}.')
    
    return children


def get_parent_dirs(element_ids):
    new_elements = []
    for id_ in element_ids:
        try:
            dir_ = Directory.objects.get(pk=id_)
            if int(dir_.index_code.code) == -10:
                if dir_.parent not in element_ids:
                    dir10 = Directory.objects.get(pk=dir_.parent)
                    dir9 = Directory.objects.get(pk=dir10.parent)
                    dir8 = Directory.objects.get(pk=dir9.parent)
                    dir7 = Directory.objects.get(pk=dir8.parent)
                    dir6 = Directory.objects.get(pk=dir7.parent)
                    dir5 = Directory.objects.get(pk=dir6.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir10.id)
                    new_elements.append(dir9.id)
                    new_elements.append(dir8.id)
                    new_elements.append(dir7.id)
                    new_elements.append(dir6.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -9:
                if dir_.parent not in element_ids:
                    dir9 = Directory.objects.get(pk=dir_.parent)
                    dir8 = Directory.objects.get(pk=dir9.parent)
                    dir7 = Directory.objects.get(pk=dir8.parent)
                    dir6 = Directory.objects.get(pk=dir7.parent)
                    dir5 = Directory.objects.get(pk=dir6.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir9.id)
                    new_elements.append(dir8.id)
                    new_elements.append(dir7.id)
                    new_elements.append(dir6.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -8:
                if dir_.parent not in element_ids:
                    dir8 = Directory.objects.get(pk=dir_.parent)
                    dir7 = Directory.objects.get(pk=dir8.parent)
                    dir6 = Directory.objects.get(pk=dir7.parent)
                    dir5 = Directory.objects.get(pk=dir6.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir8.id)
                    new_elements.append(dir7.id)
                    new_elements.append(dir6.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -7:
                if dir_.parent not in element_ids:
                    dir7 = Directory.objects.get(pk=dir_.parent)
                    dir6 = Directory.objects.get(pk=dir7.parent)
                    dir5 = Directory.objects.get(pk=dir6.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir7.id)
                    new_elements.append(dir6.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -6:
                if dir_.parent not in element_ids:
                    dir6 = Directory.objects.get(pk=dir_.parent)
                    dir5 = Directory.objects.get(pk=dir6.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir6.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -5:
                if dir_.parent not in element_ids:
                    dir5 = Directory.objects.get(pk=dir_.parent)
                    dir4 = Directory.objects.get(pk=dir5.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir5.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -4:
                if dir_.parent not in element_ids:
                    dir4 = Directory.objects.get(pk=dir_.parent)
                    dir3 = Directory.objects.get(pk=dir4.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir4.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -3:
                if dir_.parent not in element_ids:
                    dir3 = Directory.objects.get(pk=dir_.parent)
                    bus = Directory.objects.get(name=dir_.business.code, parent=0)
                    bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                    new_elements.append(dir3.id)
                    new_elements.append(bic.id)
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -2:
                bus = Directory.objects.get(name=dir_.business.code, parent=0)
                bic = Directory.objects.get(name=dir_.bic.directory_name, business=dir_.business.code, parent=bus.id)
                if bic.id not in element_ids:
                    new_elements.append(bic.id)
                if bus.id not in element_ids:
                    new_elements.append(bus.id)
            elif int(dir_.index_code.code) == -1:
                bus = Directory.objects.get(name=dir_.business.code, parent=0)
                if bus.id not in element_ids:
                    new_elements.append(bus.id)
        except Exception as e:
            logger.error(e)
            logger.error(f'or it looks like some directories are missing.')
    final_elements = element_ids
    for ne in new_elements:
        final_elements.append(ne)
    return final_elements


def get_user_differences(first_user, second_user):
    fud = first_user.__dict__
    sud = second_user.__dict__
    diff = []
    for attr in fud:
        if attr not in ['_state', 'id', 'is_confirmed', 'created_at', 'modified_at']:
            if fud[attr] != sud[attr]:
                diff.append({'field': [attr, fud[attr], sud[attr]]})
    fub = first_user.business.all()
    sub = second_user.business.all()
    bus_diff = []
    for fbus in fub:
        if not sub.filter(code=fbus.code).exists():
            bus_diff.append(fbus.description)
    if len(bus_diff) > 0:
        diff.append({'field': ['business', bus_diff, list(sbus.description for sbus in sub)]})
    
    return diff


def create_default_permission(isc_user, mftuser, last_dir, business=None, home_dir=False, preconfirmed=False):
    directory = last_dir
    list_perm = DirectoryPermissionCode.objects.get(value=256)
    while directory.parent != 0:
        if not Permission.objects.filter(user=mftuser, directory=directory, permission=list_perm.value).exists():
            perm = Permission(
                user=mftuser,
                directory=directory,
                permission=list_perm.value,
                is_confirmed=preconfirmed,
                created_by=isc_user
            )
            perm.save()
        directory = Directory.objects.get(pk=directory.parent)
    
    if home_dir:
        if mftuser.organization.code == 'ISC':
            bus_dir = Directory.objects.get(business=business, relative_path=business.code)
            for dir_ in Directory.objects.filter(parent=bus_dir.id):
                if not Permission.objects.filter(user=mftuser, directory=dir_, permission=list_perm.value).exists():
                    perm = Permission(
                        user=mftuser,
                        directory=dir_,
                        permission=list_perm.value,
                        is_confirmed=preconfirmed,
                        created_by=isc_user
                    )
                    perm.save()

        if not Permission.objects.filter(user=mftuser, directory=directory, permission=list_perm.value).exists():
            perm = Permission(
                user=mftuser,
                directory=directory,
                permission=list_perm.value,
                is_confirmed=preconfirmed,
                created_by=isc_user
            )
            perm.save()


def check_directory_tree_permission(isc_user, mftuser, is_confirmed=False):
    user_dirs = Permission.objects.filter(~Q(permission=256), user=mftuser, directory__children='').values('directory').distinct()
    for dir_ in Directory.objects.filter(pk__in=[ud['directory'] for ud in user_dirs]):
        current_dir = Directory.objects.get(pk=dir_.parent) #dir_
        dir_index = int(current_dir.index_code.code)
        while dir_index <= 0:
            non_list_perms = Permission.objects.filter(directory=current_dir, user=mftuser)
            if non_list_perms.filter(~Q(permission=256)).exists():
                non_list_perms.delete()
            if not non_list_perms.filter(permission=256).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=current_dir,
                    permission=256,
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if int(current_dir.index_code.code) == 0:
                # break
                dir_index = 1
            else:
                current_dir = Directory.objects.get(pk=current_dir.parent)
                dir_index = int(current_dir.index_code.code)


def check_directories_minimum_permissions(isc_user, mftuser, is_confirmed=False):
    dirs_with_no_child = Permission.objects.filter(~Q(permission=256), directory__children='', user=mftuser).values('directory').distinct()
    for dir_ in Directory.objects.filter(pk__in=[ud['directory'] for ud in dirs_with_no_child]):
        if not Permission.objects.filter(directory=dir_, user=mftuser, permission=0).exists():
            Permission.objects.create(
                user=mftuser,
                directory=dir_,
                permission=0, #ApplySubfolder
                is_confirmed=is_confirmed,
                created_by=isc_user
            )
        if Permission.objects.filter(directory=dir_, user=mftuser, permission=1).exists(): #Download
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=128).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=128, #Checksum
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=256).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=256, #List
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1024).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=1024, #Append
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
        if Permission.objects.filter(directory=dir_, user=mftuser, permission=2).exists(): #Upload
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=128).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=128, #Checksum
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=256).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=256, #List
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1024).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=1024, #Append
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=512).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=512, #Overwrite
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
        if Permission.objects.filter(directory=dir_, user=mftuser, permission=32).exists(): #Delete (Modify)
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=1, #Download
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=2).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=2, #Upload
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=8).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=8, #Rename
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=128).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=128, #Checksum
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=256).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=256, #List
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=512).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=512, #Overwrite
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
            if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1024).exists():
                Permission.objects.create(
                    user=mftuser,
                    directory=dir_,
                    permission=1024, #Append
                    is_confirmed=is_confirmed,
                    created_by=isc_user
                )
    all_dirs = Permission.objects.filter(user=mftuser).values('directory').distinct()
    for dir_ in Directory.objects.filter(pk__in=[ud['directory'] for ud in all_dirs]):
        dir_perms = Permission.objects.filter(directory=dir_, user=mftuser)
        if dir_perms.count() == 1:
            p = dir_perms.first()
            if p.permission != 256:
                p.delete()
            else:
                if dir_.children == '':
                    p.delete()
                else:
                    chs = [int(c) for c in dir_.children.split(',')[:-1]]
                    if not Permission.objects.filter(directory__pk__in=chs, user=mftuser).exists():
                        p.delete()


def check_parents_permission(isc_user, mftuser, parent): #, permission
    directory = None
    while parent != 0:
        directory = Directory.objects.get(pk=parent)
        if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
            perm = Permission(
                user=mftuser,
                directory=directory,
                permission=256, # List (مشاهده)
                created_by=isc_user
            )
            perm.save()
            # Permission.objects.create(
            #     user=mftuser,
            #     directory=parent,
            #     permission=128, #Checksum
            #     created_by=isc_user
            # )
        parent = directory.parent
    if not Permission.objects.filter(user=mftuser, directory=directory, permission=256).exists():
        Permission.objects.create(
            user=mftuser,
            directory=directory,
            permission=256, # List (مشاهده)
            created_by=isc_user
        )


def delete_dir_and_clean_sub_directories(dir_):
    Permission.objects.filter(directory=dir_).delete()
    if dir_.children != '':
        temp = dir_.children.split(',')
        temp.pop()
        chs = [int(t) for t in temp]
        chs_dirs = Directory.objects.filter(id__in=chs)
        for cd in chs_dirs:
            delete_dir_and_clean_sub_directories(cd)
    if dir_.parent != 0:
        chs = Directory.objects.get(pk=dir_.parent).children
        Directory.objects.filter(pk=dir_.parent).update(
            children=chs.replace(f'{str(dir_.id)},', '')
        )
    dir_.delete()


def change_all_sub_directories_relative_path(children, parent_relative_path):
    chs = [int(c) for c in children.split(',')[:-1]]
    for ch in Directory.objects.filter(pk__in=chs):
        ch.relative_path = f'{parent_relative_path}/{ch.name}'
        ch.save()
        if ch.children != '':
            change_all_sub_directories_relative_path(ch.children, ch.relative_path)


def make_username_old(firstname, lastname, delimiter):
    cleaned_firstname = firstname.replace(' ', '').lower()
    cleaned_lastname = lastname.replace(' ', '').lower()
    if MftUser.objects.filter(lastname__exact=lastname):
        if MftUser.objects.filter(firstname__exact=firstname):
            username = f'{cleaned_firstname}{delimiter}{cleaned_lastname}{str(random.randint(1, 100))}'
        else:
            if MftUser.objects.filter(username__startswith=cleaned_firstname[0]):
                if ' ' in firstname:
                    temp = firstname.lower().split(' ')
                    if MftUser.objects.filter(username__startswith=f'{temp[0][0]}{temp[1][0]}'):
                        if MftUser.objects.filter(username__startswith=cleaned_firstname[:2]):
                            username = f'{cleaned_firstname}{delimiter}{cleaned_lastname}'
                            if MftUser.objects.filter(username__exact=username):
                                username = username + str(random.randint(1, 100))
                        else:
                            username = f'{cleaned_firstname[:2]}{delimiter}{cleaned_lastname}'
                    else:
                        username = f'{temp[0][0]}{temp[1][0]}{delimiter}{cleaned_lastname}'
                else:
                    if MftUser.objects.filter(username__startswith=cleaned_firstname[:2]):
                        username = f'{cleaned_firstname}{delimiter}{cleaned_lastname}'
                        if MftUser.objects.filter(username__exact=username):
                            username = username + str(random.randint(1, 100))
                    else:
                        username = f'{cleaned_firstname[:2]}{delimiter}{cleaned_lastname}'
            else:
                username = f'{cleaned_firstname[0]}{delimiter}{cleaned_lastname}'
    else:
        username = f'{cleaned_firstname[0]}{delimiter}{cleaned_lastname}'
        if MftUser.objects.filter(username__exact=username):
            username = username + str(random.randint(1, 100))
    
    return username


def make_username(firstname, lastname, delimiter):
    cleaned_firstname = firstname.replace(' ', '').lower()
    cleaned_lastname = lastname.replace(' ', '').lower()
    i = 1
    while i <= len(firstname):
        username = f'{cleaned_firstname[:i]}{delimiter}{cleaned_lastname}'
        if not MftUser.objects.filter(username__exact=username).exists():
            return username
        i += 1

    username = f'{cleaned_firstname[0]}{delimiter}{cleaned_lastname}'
    while True:
        new_username = username + str(random.randint(1, 100))
        if not MftUser.objects.filter(username__exact=new_username):
            return new_username


def export_user(id, isc_user):
    mftuser = MftUser.objects.get(pk=id)
    template = ET.parse(os.path.join(settings.MEDIA_ROOT, 'template.xml'))
    description = template.xpath('//webUsers/webUser/description')
    description[0].text = mftuser.description
    email = template.xpath('//webUsers/webUser/email')
    email[0].text = mftuser.email
    firstName = template.xpath('//webUsers/webUser/firstName')
    firstName[0].text = mftuser.firstname
    phone = template.xpath('//webUsers/webUser/phone')
    phone[0].text = str(mftuser.officephone)
    authenticationAlias = template.xpath('//webUsers/webUser/authenticationAlias')
    authenticationAlias[0].text = mftuser.alias
    lastName = template.xpath('//webUsers/webUser/lastName')
    lastName[0].text = mftuser.lastname
    organization = template.xpath('//webUsers/webUser/organization')
    organization[0].text = f'{mftuser.organization.description} - {mftuser.created_by.department.description}' if mftuser.organization.code == 'ISC' else mftuser.organization.description
    mobilePhone = template.xpath('//webUsers/webUser/mobilePhone')
    mobilePhone[0].text = str(mftuser.mobilephone)
    name = template.xpath('//webUsers/webUser/name')
    name[0].text = mftuser.username
    # <ipFilterEntries>
    #     <ipFilterEntry>
    #         <address></address>
    #     </ipFilterEntry>
    # </ipFilterEntries>
    # ip = template.xpath('//webUsers/webUser/ipFilterEntries/ipFilterEntry/address')
    # ip[0].text = mftuser.ipaddr
    virtualFile = template.xpath('//webUsers/webUser/virtualFile')
    virtual_files = template.xpath('//webUsers/webUser/virtualFile/virtualFiles')
    permissions = Permission.objects.filter(user=mftuser, is_confirmed=True)
    all_dirs = permissions.values('directory').distinct()
    # bus_codes = [ub.code for ub in mftuser.business.all()]
    # bus_dirs = Directory.objects.filter(name__in=bus_codes)
    bus_dirs = []
    for d in all_dirs:
        dir_ = Directory.objects.get(pk=d['directory'])
        if dir_.parent == 0:
            bus_dirs.append(dir_)
    for bus_dir in bus_dirs:
        virtual_file = ET.SubElement(virtual_files[0], 'virtualFile')
        make_virtual_file(bus_dir, permissions, virtual_file)
        # chs = bus_dir.children.split(',')[:-1]
        # dirs_with_perms = [dir_['directory'] for dir_ in all_dirs if str(dir_['directory']) in chs]
        # for d in dirs_with_perms:
        #     virtual_file = ET.SubElement(virtual_files[0], 'virtualFile')
        #     make_virtual_file(Directory.objects.get(pk=d), permissions, virtual_file)
    
    temp_file = ntf(mode='w+', encoding='utf-8', delete=True)
    bytes_template = ET.tostring(template)
    temp_file.write(bytes_template.decode('utf-8'))
    temp_file.flush()
    webuser_file = File(temp_file, name=f'{mftuser.username}.xml')
    if ReadyToExport.objects.filter(mftuser=mftuser).exists():
        rte = ReadyToExport.objects.get(mftuser=mftuser)
        # rte.is_downloaded = False
        rte.number_of_exports = rte.number_of_exports + 1
        # if os.path.isfile(rte.export.path):
        os.remove(rte.export.path)
        rte.export = webuser_file
        rte.save()
        # rte.delete()
    else:
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml')):
            os.remove(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml'))
        ReadyToExport.objects.create(
            mftuser=mftuser,
            created_by=isc_user,
            export=webuser_file
            # is_downloaded=False,
            # number_of_exports=1,
            # number_of_downloads=0,
        )


def export_user_with_paths(id, isc_user):
    mftuser = MftUser.objects.get(pk=id)
    template = ET.parse(os.path.join(settings.MEDIA_ROOT, 'template.xml'))
    description = template.xpath('//webUsers/webUser/description')
    description[0].text = mftuser.description
    email = template.xpath('//webUsers/webUser/email')
    email[0].text = mftuser.email
    firstName = template.xpath('//webUsers/webUser/firstName')
    firstName[0].text = mftuser.firstname
    phone = template.xpath('//webUsers/webUser/phone')
    phone[0].text = str(mftuser.officephone)
    authenticationAlias = template.xpath('//webUsers/webUser/authenticationAlias')
    authenticationAlias[0].text = mftuser.alias
    lastName = template.xpath('//webUsers/webUser/lastName')
    lastName[0].text = mftuser.lastname
    organization = template.xpath('//webUsers/webUser/organization')
    organization[0].text = f'{mftuser.organization.description} - {mftuser.created_by.department.description}' if mftuser.organization.code == 'ISC' else mftuser.organization.description
    mobilePhone = template.xpath('//webUsers/webUser/mobilePhone')
    mobilePhone[0].text = str(mftuser.mobilephone)
    name = template.xpath('//webUsers/webUser/name')
    name[0].text = mftuser.username
    # <ipFilterEntries>
    #     <ipFilterEntry>
    #         <address></address>
    #     </ipFilterEntry>
    # </ipFilterEntries>
    # ip = template.xpath('//webUsers/webUser/ipFilterEntries/ipFilterEntry/address')
    # ip[0].text = mftuser.ipaddr
    virtualFile = template.xpath('//webUsers/webUser/virtualFile')
    virtual_files = template.xpath('//webUsers/webUser/virtualFile/virtualFiles')
    permissions = Permission.objects.filter(user=mftuser, is_confirmed=True).exclude(directory__index_code__code='-1', directory__children='')
    all_dirs = permissions.values('directory').distinct()
    # bus_codes = [ub.code for ub in mftuser.business.all()]
    # bus_dirs = Directory.objects.filter(name__in=bus_codes)
    bus_dirs = []
    for d in all_dirs:
        dir_ = Directory.objects.get(pk=d['directory'])
        if dir_.parent == 0:
            bus_dirs.append(dir_)
    for bus_dir in bus_dirs:
        virtual_file = ET.SubElement(virtual_files[0], 'virtualFile')
        make_virtual_file(bus_dir, permissions, virtual_file)
        # chs = bus_dir.children.split(',')[:-1]
        # dirs_with_perms = [dir_['directory'] for dir_ in all_dirs if str(dir_['directory']) in chs]
        # for d in dirs_with_perms:
        #     virtual_file = ET.SubElement(virtual_files[0], 'virtualFile')
        #     make_virtual_file(Directory.objects.get(pk=d), permissions, virtual_file)
    
    webuser_temp_file = ntf(mode='w+', encoding='utf-8', delete=True)
    bytes_template = ET.tostring(template, pretty_print=True)
    webuser_temp_file.write(bytes_template.decode('utf-8'))
    webuser_temp_file.flush()
    webuser_file = File(webuser_temp_file, name=f'{mftuser.username}.xml')
    paths_temp_file = ntf(mode='w+', encoding='utf-8', delete=True)
    dir_ids = [d['directory'] for d in all_dirs]
    for d in Directory.objects.filter(pk__in=dir_ids).order_by('relative_path'):
        paths_temp_file.write(f'{d.absolute_path},\n')
    paths_temp_file.flush()
    paths_file = File(paths_temp_file, name=f'{mftuser.username}.csv')
    # csv_file_path, csv_file_name = make_csv_of_single_user_paths(all_dirs, name=mftuser.username)
    if ReadyToExport.objects.filter(mftuser=mftuser).exists():
        rte = ReadyToExport.objects.get(mftuser=mftuser)
        # rte.is_downloaded = False
        rte.number_of_exports = rte.number_of_exports + 1
        # if os.path.isfile(rte.export.path):
        # os.remove(rte.webuser.path)
        # os.remove(rte.paths.path)
        rte.webuser = webuser_file
        rte.paths = paths_file
        rte.save()
        # rte.delete()
    else:
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml')):
            os.remove(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml'))
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.csv')):
            os.remove(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.csv'))
        ReadyToExport.objects.create(
            mftuser=mftuser,
            created_by=isc_user,
            webuser=webuser_file,
            paths=paths_file
            # is_downloaded=False,
            # number_of_exports=1,
            # number_of_downloads=0,
        )


def export_user_with_paths_v2(mftuser, isc_user):
    template_name = ''
    is_foreign_mftuser = None
    if mftuser.organization.sub_domain == DomainName.objects.get(code='nibn.ir'):
        template_name = 'default_mftuser_template.xml'
        is_foreign_mftuser = False
    else:
        template_name = 'foreign_mftuser_template.xml'
        is_foreign_mftuser = True
    template = ET.parse(os.path.join(settings.MEDIA_ROOT, template_name))
    description = template.xpath('//webUsers/webUser/description')
    description[0].text = mftuser.description
    email = template.xpath('//webUsers/webUser/email')
    email[0].text = mftuser.email
    firstName = template.xpath('//webUsers/webUser/firstName')
    firstName[0].text = mftuser.firstname
    phone = template.xpath('//webUsers/webUser/phone')
    phone[0].text = str(mftuser.officephone)
    authenticationAlias = template.xpath('//webUsers/webUser/authenticationAlias')
    authenticationAlias[0].text = mftuser.alias
    lastName = template.xpath('//webUsers/webUser/lastName')
    lastName[0].text = mftuser.lastname
    organization = template.xpath('//webUsers/webUser/organization')
    organization[0].text = f'{mftuser.organization.description} - {mftuser.created_by.department.description}' if mftuser.organization.code == 'ISC' else mftuser.organization.description
    mobilePhone = template.xpath('//webUsers/webUser/mobilePhone')
    mobilePhone[0].text = str(mftuser.mobilephone)
    name = template.xpath('//webUsers/webUser/name')
    name[0].text = mftuser.username
    # <ipFilterEntries>
    #     <ipFilterEntry>
    #         <address></address>
    #     </ipFilterEntry>
    # </ipFilterEntries>
    # ip = template.xpath('//webUsers/webUser/ipFilterEntries/ipFilterEntry/address')
    # ip[0].text = mftuser.ipaddr
    virtualFile = template.xpath('//webUsers/webUser/virtualFile')
    virtual_files = template.xpath('//webUsers/webUser/virtualFile/virtualFiles')
    # for bus in mftuser.business.all():
    #     if not Permission.objects.filter(user=mftuser, directory__parent=0, directory__business=bus).exists():
    #         Permission.objects.create(
    #             user=mftuser,
    #             directory=Directory.objects.get(business=bus, parent=0),
    #             permission=256, # List (مشاهده)
    #             created_by=isc_user,
    #             is_confirmed=True
    #         )
    # check_directory_tree_permission(isc_user=isc_user, mftuser=mftuser, is_confirmed=True)
    permissions = Permission.objects.filter(user=mftuser, is_confirmed=True).exclude(directory__index_code__code='-1', directory__children='')
    for item in permissions.filter(directory__index_code__code='-1'):
        if not permissions.filter(directory__id__in=[int(i) for i in item.directory.children.split(',')[:-1]]).exists():
            permissions = permissions.exclude(directory__id=item.directory.id)
    for bus_dir in list(permissions.filter(directory__parent=0).values('directory').distinct()):
        virtual_file = ET.SubElement(virtual_files[0], 'virtualFile')
        make_virtual_file(Directory.objects.get(pk=bus_dir['directory']), permissions, virtual_file, foreign_user=is_foreign_mftuser)
    webuser_temp_file = ntf(mode='w+', encoding='utf-8', delete=True)
    bytes_template = ET.tostring(template, pretty_print=True)
    webuser_temp_file.write(bytes_template.decode('utf-8'))
    webuser_temp_file.flush()
    webuser_file = File(webuser_temp_file, name=f'{mftuser.username}.xml')
    paths_temp_file = ntf(mode='w+', encoding='utf-8', delete=True)
    for d in Directory.objects.filter(pk__in=[dir_['directory'] for dir_ in Permission.objects.filter(user=mftuser, is_confirmed=True).values('directory')]).order_by('relative_path'):
        paths_temp_file.write(f'{d.relative_path},\n')
    paths_temp_file.flush()
    paths_file = File(paths_temp_file, name=f'{mftuser.username}.csv')
    if ReadyToExport.objects.filter(mftuser=mftuser).exists():
        rte = ReadyToExport.objects.get(mftuser=mftuser)
        rte.number_of_exports = rte.number_of_exports + 1
        rte.webuser = webuser_file
        rte.paths = paths_file
        rte.save()
    else:
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml')):
            os.remove(os.path.join(settings.MEDIA_ROOT, 'exports', f'{mftuser.username}.xml'))
        ReadyToExport.objects.create(
            mftuser=mftuser,
            created_by=isc_user,
            webuser=webuser_file,
            paths=paths_file
        )


def make_virtual_file(directory, permissions, virtual_file, foreign_user=False):
    all_dirs = permissions.values('directory').distinct()
    summed = permissions.filter(directory=directory).aggregate(Sum('permission'))
    _type = ET.SubElement(virtual_file, 'type')
    _type.text = 'D'
    _alias = ET.SubElement(virtual_file, 'alias')
    _alias.text = directory.name
    _filePermissions = ET.SubElement(virtual_file, 'filePermissions')
    _filePermissions.text = '0'
    _folderPermissions = ET.SubElement(virtual_file, 'folderPermissions')
    _folderPermissions.text = str(summed['permission__sum'])
    _applyToSubfolders = ET.SubElement(virtual_file, 'applyToSubfolders')
    if permissions.filter(directory=directory, permission=0).exists():
        _applyToSubfolders.text = 'true'
    else:
        _applyToSubfolders.text = 'false'
    _diskQuotaOption = ET.SubElement(virtual_file, 'diskQuotaOption')
    _diskQuotaOption.text = 'N'
    _diskQuotaSize = ET.SubElement(virtual_file, 'diskQuotaSize')
    _diskQuotaSize.text = '0'
    _diskQuotaUnit = ET.SubElement(virtual_file, 'diskQuotaUnit')
    _diskQuotaUnit.text = 'M'
    _path = ET.SubElement(virtual_file, 'path')
    dir_path = ''
    if foreign_user:
        dir_path = directory.foreign_path
    else:
        if directory.bic.sub_domain == DomainName.objects.get(code='nibn.ir'):
            dir_path = directory.absolute_path
        else:
            dir_path = directory.remote_path
    _path.text = dir_path
    virtual_files = ET.SubElement(virtual_file, 'virtualFiles')
    chs = directory.children.split(',')[:-1]
    dirs_with_perms = [dir_['directory'] for dir_ in all_dirs if str(dir_['directory']) in chs]
    for d in dirs_with_perms:
        vf = ET.SubElement(virtual_files, 'virtualFile')
        make_virtual_file(Directory.objects.get(pk=d), permissions, vf, foreign_user=foreign_user)


def zip_all_exported_users(name='export'):
    path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.zip')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        all_exported = ReadyToExport.objects.all()
        for ef in all_exported:
            if os.path.exists(ef.webuser.path):
                zf.write(ef.webuser.path, arcname=ef.webuser.name.split('/')[-1])
            else:
                logger.error(f'file in {ef.webuser.path} does not exists, it looks like it belongs to {ef.mftuser.username} mftuser.')
            if os.path.exists(ef.paths.path):
                zf.write(ef.paths.path, arcname=ef.paths.name.split('/')[-1])
            else:
                logger.error(f'file in {ef.paths.path} does not exists, it looks like it belongs to {ef.mftuser.username} mftuser.')
        # return zf
    return os.path.join(os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.zip'))


def make_csv_of_all_paths(name='paths'):
    path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.csv')
    with open(path, mode='w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', lineterminator='\n')
        csv_writer.writerow(['PATHS'])
        for d in Directory.objects.all().order_by('relative_path'):
            csv_writer.writerow([f'{d.absolute_path}'])
            
    return os.path.join(os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.csv'))


def make_report_in_csv_format(dir_default_depth, name='report'):
    all_buss = BusinessCode.objects.all().order_by('description')
    path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.csv')
    with open(path, mode='w', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', lineterminator='\n')
        csv_writer.writerow(['پروژه/سامانه', f"تعداد دایرکتوری های لایه {dir_default_depth}", 'تعداد کاربران'])
        for bus in all_buss:
            csv_writer.writerow([
                bus.description,
                Directory.objects.filter(
                    business=bus,
                    index_code=DirectoryIndexCode.objects.get(code=f'-{str(dir_default_depth)}')
                ).count(),
                MftUser.objects.filter(business=bus).count()
            ])
            
    return os.path.join(os.path.join(settings.MEDIA_ROOT, 'exports', f'{name}.csv'))


def export_users_with_sftp(files_list, dest):
    tp = paramiko.Transport((settings.SFTP_HOST, int(settings.SFTP_PORT)))
    tp.connect(username=settings.SFTP_USERNAME, password=settings.SFTP_PASSWORD)
    sftp_client = paramiko.SFTPClient.from_transport(tp)
    sftp_client.chdir(dest)
    for file in files_list:
        # split by '/' in linux
        sftp_client.put(file, file.split('/')[-1])
        # split by '\' in windows
        # sftp_client.put(file, file.split('\\')[-1])
    sftp_client.close()


def make_form_from_invoice(invoice, contents):
    html_path = os.path.join(settings.MEDIA_ROOT, 'form-307.html')
    html_root = html.parse(html_path).getroot()
    date = html_root.get_element_by_id("date")
    date.text = jdt.now().strftime('%Y/%m/%d')
    serial_number = html_root.get_element_by_id("invoice-holder")
    serial_number.text = invoice.serial_number
    counter = html_root.get_element_by_id("counter")
    counter.text = str(Invoice.objects.filter(mftuser=invoice.mftuser).count())
    #TODO: correct contents html formatting and write to file
    invoice_contents = html_root.get_element_by_id("form-contents")
    invoice_contents.text = html.tostring(html.fromstring(contents))
    pdf_path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{invoice.get_mftuser().username}.pdf')
    new_html_path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{invoice.get_mftuser().username}.html')
    with open(new_html_path, mode='w+') as html_temp_file:
        bytes_html = html.tostring(html_root, pretty_print=True)
        html_temp_file.write(bytes_html.decode('utf-8'))
        #TODO: pdf is empty! make it right
        pdfkit.from_file(html_temp_file, pdf_path)
    # os.remove(new_html_path)
    return pdf_path


def confirm_directory_tree(ids_list, survey='FORWARD'):
    dirs = Directory.objects.filter(pk__in=ids_list)
    for dir_ in dirs:
        if survey == 'FORWARD':
            dir_.is_confirmed = True
            dir_.save()
            children = Directory.objects.filter(pk__in=[int(id_) for id_ in dir_.children.split(',')[:-1]])
            children_ids = [ch['id'] for ch in children.values('id')]
            confirm_directory_tree(children_ids)
        elif survey == 'BACKWARD':
            if dir_.parent != 0:
                parent = Directory.objects.get(pk=dir_.parent)
                parent.is_confirmed = True
                parent.save()
                confirm_directory_tree([parent.parent], survey='BACKWARD')


def insert_into_db():
    iscuser = IscUser.objects.get(pk=1)

    bank_dir_names = {
        'Ansar': 'ANSBIRTHXXX',
        'Ayandeh': 'AYBKIRTHXXX',
        'EghtesadNovin': 'BEGNIRTHXXX',
        'Pasargad': 'BKBPIRTHXXX',
        'Maskan': 'BKMNIRTHXXX',
        'Mellat': 'BKMTIRTHXXX',
        'Parsian': 'BKPAIRTHXXX',
        'SanatOMadan': 'BOIMIRTHXXX',
        'Saderat': 'BSIRIRTHXXX',
        'Tejarat': 'BTEJIRTHXXX',
        'Tosse': 'BTOSIRTHXXX',
        'Caspian': 'CASPIRTHXXX',
        'Shahr': 'CIYBIRTHXXX',
        'Day': 'DAYBIRTHXXX',
        'TosseSaderat': 'EDBIIRTHXXX',
        'IranEuropa': 'EIHBIRTHXXX',
        'Ghavamin': 'GHVMIRTHXXX',
        'IranZamin': 'IRZAIRTHXXX',
        'IranVenezoela': 'IVBBIRTHXXX',
        'Karafarin': 'KBIDIRTHXXX',
        'Keshavarzi': 'KESHIRTHXXX',
        'Khavarmiyaneh': 'KHMIIRTHXXX',
        'Kosar': 'KSACIRTHXXX',
        'ISC': 'MACDIRTHXXX',
        'ISC': 'SIAMIRTHXXX',
        'ISC': 'ISCOIRTHXXX',
        'Markazi': 'BMJIIRTHXXX',
        'Markazi': 'BMJJIRTHXXX',
        'Mehr': 'MEHRIRTHXXX',
        'Melli': 'MELIIRTHXXX',
        'Noor': 'NOORIRTHXXX',
        'PostBank': 'PBIRIRTHXXX',
        'Refah': 'REFAIRTHXXX',
        'Resalat': 'RESAIRTHXXX',
        'Saman': 'SABCIRTHXXX',
        'Sepah': 'SEPBIRTHXXX',
        'Sina': 'SINAIRTHXXX',
        'Sarmayeh': 'SRMBIRTHXXX',
        'Gardeshgari': 'TOSMIRTHXXX',
        'Melal': 'TOUSIRTHXXX',
        'TosseTaavon': 'TTBIIRTHXXX',
    }

    dir_list = [
        {'name': 'Offline_process', 'parent': 'bank'},
        {'name': 'in', 'parent': 'bic_dir'},
        {'name': 'accepted', 'parent': 'in'},
        {'name': 'out', 'parent': 'bic_dir'},
    ]

    mftusers_list = [
        'a_ansari',
        'a_bakhtiari',
        'a_rezvanpour',
        'a_sedighi',
        'b_hafezi',
        'h_enayati',
        'h_ravanshad',
        'k_ghorbani',
        'k_zabeti',
        'm_babakhanian',
        'm_babanejad',
        'm_eini',
        'm_haghighat',
        'm_omidi',
        'm_taheri',
        'o_rouein',
        'p_bahrami',
        'p_norouzimanesh',
        'p_vahebzadeh',
        'r_kazemi',
        's_jamshidi'
    ]

    #####
        # for bus in BusinessCode.objects.all().order_by('code'):
        #     dir_ = Directory(
        #         name=bus.code,
        #         relative_path=bus.code,
        #         index_code=DirectoryIndexCode.objects.get(code=0),
        #         parent=0,
        #         business=bus,
        #         bic=BankIdentifierCode.objects.get(code='BMJI'),
        #         created_by=IscUser.objects.get(pk=1)
        #     )
        #     dir_.save()
        #     for bic in BankIdentifierCode.objects.all().order_by('code'):
        #         ch_dir = Directory(
        #             name=bic.directory_name,
        #             relative_path=f'{bus.code}/{bic.directory_name}',
        #             index_code=DirectoryIndexCode.objects.get(code=-1),
        #             parent=dir_.id,
        #             business=bus,
        #             bic=bic,
        #             created_by=IscUser.objects.get(pk=1)
        #         )
        #         ch_dir.save()
        #         dir_.children += f'{ch_dir.id},'
        #     dir_.save()

        # for mftuser in MftUser.objects.all().order_by('username'):
        #     if mftuser.organization.code == 'ISC':
        #         for bus in mftuser.business.all().order_by('code'):
        #             create_default_permission(
        #                 isc_user=iscuser,
        #                 mftuser=mftuser,
        #                 last_dir=Directory.objects.get(relative_path=f'{bus.code}/{mftuser.organization.directory_name}'),
        #                 business=bus,
        #                 home_dir=True
        #                 )

        # for d in dir_list:
        #     dir_ = Directory.objects.get(name=d, parent=1028)
        #     chs = [int(dc) for dc in dir_.children.split(',')[:-1]]
        #     i = DirectoryIndexCode.objects.get(code=str(int(dir_.index_code.code) - 1))
        #     banki = Directory(
        #         name='BANKI',
        #         bic=dir_.bic,
        #         business=dir_.business,
        #         relative_path=f'{dir_.relative_path}/BANKI',
        #         parent=dir_.id,
        #         children=dir_.children,
        #         index_code=i,
        #         created_by=iscuser
        #     )
        #     banki.save()
        #     dir_.children = f'{str(banki.id)},'
        #     dir_.save()
        #     for c in chs:
        #         d_ = Directory.objects.get(pk=c)
        #         d_.parent = banki.id
        #         lower_directory_index(d_)
        #         d_.save()

    # Nahab dirs
        # for bd in Directory.objects.filter(parent=758):
        #     try:
        #         bic_dir_name = bank_dir_names[f'{bd.name}']
        #         op = Directory(
        #             name=dir_list[0]['name'],
        #             parent=bd.id,
        #             business=bd.business,
        #             bic=bd.bic,
        #             relative_path=f'{bd.relative_path}/{dir_list[0]["name"]}',
        #             index_code=DirectoryIndexCode.objects.get(code=str(int(bd.index_code.code) - 1)),
        #             created_by=iscuser
        #         )
        #         op.save()
        #         bd.children = f'{str(op.id)},'
        #         bd.save()
        #         bic_dir = Directory(
        #             name=bic_dir_name,
        #             parent=op.id,
        #             business=op.business,
        #             bic=op.bic,
        #             relative_path=f'{op.relative_path}/{bic_dir_name}',
        #             index_code=DirectoryIndexCode.objects.get(code=str(int(op.index_code.code) - 1)),
        #             created_by=iscuser
        #         )
        #         bic_dir.save()
        #         op.children = f'{str(bic_dir.id)},'
        #         op.save()
        #         in_ = Directory(
        #             name=dir_list[1]['name'],
        #             parent=bic_dir.id,
        #             business=bic_dir.business,
        #             bic=bic_dir.bic,
        #             relative_path=f'{bic_dir.relative_path}/{dir_list[1]["name"]}',
        #             index_code=DirectoryIndexCode.objects.get(code=str(int(bic_dir.index_code.code) - 1)),
        #             created_by=iscuser
        #         )
        #         in_.save()
        #         acc = Directory(
        #             name=dir_list[2]['name'],
        #             parent=in_.id,
        #             business=in_.business,
        #             bic=in_.bic,
        #             relative_path=f'{in_.relative_path}/{dir_list[2]["name"]}',
        #             index_code=DirectoryIndexCode.objects.get(code=str(int(in_.index_code.code) - 1)),
        #             created_by=iscuser
        #         )
        #         acc.save()
        #         in_.children = f'{str(acc.id)},'
        #         in_.save()
        #         out = Directory(
        #             name=dir_list[3]['name'],
        #             parent=bic_dir.id,
        #             business=bic_dir.business,
        #             bic=bic_dir.bic,
        #             relative_path=f'{bic_dir.relative_path}/{dir_list[3]["name"]}',
        #             index_code=DirectoryIndexCode.objects.get(code=str(int(bic_dir.index_code.code) - 1)),
        #             created_by=iscuser
        #         )
        #         out.save()
        #         bic_dir.children = f'{str(in_.id)},{str(out.id)},'
        #         bic_dir.save()
        #         print('|_NAHAB')
        #         print(f'|___{bd.name}')
        #         print('|_____Offline_process')
        #         print(f'|_______{bic_dir_name}')
        #         print('|_________in')
        #         print('|___________accepted')
        #         print('|_________out')
        #         print('*********************')
        #     except:
        #         print(f'{bd.name} does not exist in dict')

    # Nahab user permissions
        # for user in MftUser.objects.filter(business=BusinessCode.objects.get(code='NAHAB')):
        #     in_dir = Directory.objects.get(name='in', business=user.business.first(), bic=user.organization)
        #     out_dir = Directory.objects.get(name='out', business=user.business.first(), bic=user.organization)
        #     accepted_dir = Directory.objects.get(name='accepted', business=user.business.first(), bic=user.organization)
            
        #     create_default_permission(isc_user=iscuser, mftuser=user, last_dir=accepted_dir, home_dir=True)
            
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=1, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=1, created_by=iscuser) #Download (Read)
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=256, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=256, created_by=iscuser) #List
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=128, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=128, created_by=iscuser) #Checksum
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=1024, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=1024, created_by=iscuser) #Append

        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=2, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=2, created_by=iscuser) #Upload (Write)
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=256, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=256, created_by=iscuser) #List
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=128, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=128, created_by=iscuser) #Checksum
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=1024, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=1024, created_by=iscuser) #Append
        #     if not Permission.objects.filter(user=user, directory=in_dir, permission=512, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=in_dir, permission=512, created_by=iscuser) #Overwrite
            
        #     if not Permission.objects.filter(user=user, directory=out_dir, permission=1, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=out_dir, permission=1, created_by=iscuser) #Download (Read)
        #     if not Permission.objects.filter(user=user, directory=out_dir, permission=256, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=out_dir, permission=256, created_by=iscuser) #List
        #     if not Permission.objects.filter(user=user, directory=out_dir, permission=128, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=out_dir, permission=128, created_by=iscuser) #Checksum
        #     if not Permission.objects.filter(user=user, directory=out_dir, permission=1024, created_by=iscuser).exists():
        #         Permission.objects.create(user=user, directory=out_dir, permission=1024, created_by=iscuser) #Append

    # Nahab user invoices
        # for mftuser in MftUser.objects.filter(business=BusinessCode.objects.get(code='NAHAB')):
        #     perms_str = ''
        #     bus_dirs = Directory.objects.filter(business=BusinessCode.objects.get(code='NAHAB')).order_by('relative_path')
        #     permissions = Permission.objects.filter(user=mftuser, directory__in=bus_dirs, is_confirmed=False)
        #     if permissions.filter(permission__in=[1, 2, 32, 4]).exists():
        #         for p in permissions.values('id').distinct():
        #             perms_str += f'{p["id"]},'
        #         Invoice.objects.create(
        #             invoice_type=InvoiceType.objects.get(code='INVOBUS'),
        #             mftuser=mftuser.id,
        #             used_business=0,
        #             permissions_list=perms_str,
        #             created_by=iscuser
        #         )

    # Nahab user export
        # for invoice in Invoice.objects.filter(created_by=IscUser.objects.get(pk=1)):
        #     mftuser = MftUser.objects.get(pk=invoice.mftuser)
        #     mftuser.is_confirmed = True
        #     mftuser.save()
        #     perms_list = [int(p) for p in invoice.permissions_list.split(',')[:-1]]
        #     Permission.objects.filter(pk__in=perms_list).update(is_confirmed=True)
        #     export_user_with_paths(invoice.mftuser, iscuser)
        #     invoice.confirm_or_reject = 'CONFIRMED'
        #     invoice.save()
    
    # mftusers = MftUser.objects.filter(username__in=mftusers_list)
        # BNKIRN_dir_id = 56
        # BNKIRN_bus_id = 13
        # RFM_dir_id = 1028
        # RFM_ISC_dir_id = 1048
        # RFM_bus_id = 19
        # for inv in Invoice.objects.filter(mftuser__in=[user.id for user in mftusers], used_business=BNKIRN_bus_id, confirm_or_reject='CONFIRMED', invoice_type__code='INVUBUS'):
        # print(inv.permissions_list)
        # user = mftusers.filter(pk=inv.mftuser).first()
        # perm = Permission.objects.get(directory__id=BNKIRN_dir_id, user=user, permission=256)
        # print(f'{perm.user} - {perm.permission} on {perm.directory.relative_path}')
        # deleted_perms = []
        # for i in inv.permissions_list.split(',')[:-1]:
        #     try:
        #         perm = Permission.objects.get(pk=i)
        #         if perm.permission != 256:
        #         print(perm)
        #     except Exception as e:
        #         print(f'permission with id {i} not found')
        #         deleted_perms.append(i)
        # print(f'deleted permissions {deleted_perms}')
        # temp = inv.permissions_list
        # for i in inv.permissions_list.split(',')[:-1]:
        #     if i in deleted_perms:
        #         temp = temp.replace(f'{i},', '')
        # inv.permissions_list += f'{perm.id},'
        # inv.permissions_list = temp
        # inv.save()


def lower_directory_index(directory):
    parent = Directory.objects.get(pk=directory.parent)
    new_index = DirectoryIndexCode.objects.get(code=str(int(directory.index_code.code) - 1))
    directory.index_code = new_index
    directory.relative_path = f'{parent.relative_path}/{directory.name}'
    directory.save()
    chs = [int(dc) for dc in directory.children.split(',')[:-1]]
    for c in chs:
        lower_directory_index(Directory.objects.get(pk=c))


def clean_up(flag='', action=False, *args, **kwargs):
    if flag == '':
        print('Nothing to cleanup.')
    elif flag == 'perm':
        print('Cleanup permissions.')
        for p in Permission.objects.all():
            if not Directory.objects.filter(pk=p.directory.id).exists():
                print(f'dir with id {p.directory.id} does not exists')
                if action:
                    p.delete()
    elif flag == 'perm2':
        print('Cleanup duplicate permissions.')
        for d in Directory.objects.all():
            for u in MftUser.objects.all():
                print(f'checking {u.username} permissions on {d.name}')
                if Permission.objects.filter(user=u, directory=d, permission=0).count() > 1:
                    print(f'{u.username} has duplicate 0 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=0).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=1).count() > 1:
                    print(f'{u.username} has duplicate 1 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=1).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=2).count() > 1:
                    print(f'{u.username} has duplicate 2 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=2).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=4).count() > 1:
                    print(f'{u.username} has duplicate 4 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=4).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=8).count() > 1:
                    print(f'{u.username} has duplicate 8 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=8).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=16).count() > 1:
                    print(f'{u.username} has duplicate 16 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=16).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=32).count() > 1:
                    print(f'{u.username} has duplicate 32 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=32).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=64).count() > 1:
                    print(f'{u.username} has duplicate 64 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=64).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=128).count() > 1:
                    print(f'{u.username} has duplicate 128 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=128).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=256).count() > 1:
                    print(f'{u.username} has duplicate 256 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=256).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=512).count() > 1:
                    print(f'{u.username} has duplicate 512 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=512).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=1024).count() > 1:
                    print(f'{u.username} has duplicate 1024 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=1024).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=2048).count() > 1:
                    print(f'{u.username} has duplicate 2048 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=2048).first()
                        p.delete()
                if Permission.objects.filter(user=u, directory=d, permission=4096).count() > 1:
                    print(f'{u.username} has duplicate 4096 permission on {d.name}')
                    if action:
                        p = Permission.objects.filter(user=u, directory=d, permission=4096).first()
                        p.delete()
    elif flag == 'perm3':
        print('Cleanup permissions v3.')
        admin = IscUser.objects.get(user__username='admin')
        all_users = kwargs['all_users'] #MftUser.objects.all()
        for mftuser in all_users:
            print(f'mftuser {mftuser.username}:')
            user_dirs = Permission.objects.filter(~Q(permission=256), user=mftuser, directory__children='').values('directory').distinct()
            for dir_ in Directory.objects.filter(pk__in=[ud['directory'] for ud in user_dirs]):
                current_dir = Directory.objects.get(pk=dir_.parent)
                dir_index = int(current_dir.index_code.code)
                while dir_index <= 0:
                    non_list_perms = Permission.objects.filter(directory=current_dir, user=mftuser)
                    if non_list_perms.filter(~Q(permission=256)).exists():
                        for p in non_list_perms:
                            print(f'{p} deleted')
                        if action:
                            non_list_perms.delete()
                    if not non_list_perms.filter(permission=256).exists():
                        if action:
                            Permission.objects.create(user=mftuser, directory=current_dir, permission=256, is_confirmed=True, created_by=admin)
                        print(f'list access on {current_dir.relative_path} created')
                    if int(current_dir.index_code.code) == 0:
                        dir_index = 1
                    else:
                        current_dir = Directory.objects.get(pk=current_dir.parent)
                        dir_index = int(current_dir.index_code.code)
    elif flag == 'perm4':
        print('Cleanup permissions v4.')
        isc_user = IscUser.objects.get(user__username='admin')
        all_users = kwargs['all_users'] #MftUser.objects.all()
        for mftuser in all_users:
            print(f'mftuser {mftuser.username}:')
            dirs_with_no_child = Permission.objects.filter(~Q(permission=256), directory__children='', user=mftuser).values('directory').distinct()
            for dir_ in Directory.objects.filter(pk__in=[ud['directory'] for ud in dirs_with_no_child]):
                if not Permission.objects.filter(directory=dir_, user=mftuser, permission=0).exists():
                    print(f'ApplySubfolder access on {dir_.relative_path} created')
                    if action:
                        Permission.objects.create(
                            user=mftuser,
                            directory=dir_,
                            permission=0, #ApplySubfolder
                            is_confirmed=True,
                            created_by=isc_user
                        )
                if Permission.objects.filter(directory=dir_, user=mftuser, permission=32).exists(): #Delete (Modify)
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1).exists():
                        print(f'Download access on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=1, #Download
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=2).exists():
                        print(f'Upload access on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=2, #Upload
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=8).exists():
                        print(f'Rename access on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=8, #Rename
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=128).exists():
                        print(f'Download Checksum on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=128, #Checksum
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=256).exists():
                        print(f'Download List on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=256, #List
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=512).exists():
                        print(f'Download Overwrite on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=512, #Overwrite
                                is_confirmed=True,
                                created_by=isc_user
                            )
                    if not Permission.objects.filter(user=mftuser, directory=dir_, permission=1024).exists():
                        print(f'Download Append on {dir_.relative_path} created')
                        if action:
                            Permission.objects.create(
                                user=mftuser,
                                directory=dir_,
                                permission=1024, #Append
                                is_confirmed=True,
                                created_by=isc_user
                            )
    elif flag == 'perm5':
        print('Cleanup permissions v5.')
        isc_user = IscUser.objects.get(user__username='admin')
        for p in Permission.objects.filter(~Q(directory__children='') & ~Q(directory__business__code='NAHAB') & ~Q(permission=256)):
            print(f'{p.user.username} has more than LIST access on {p.directory.relative_path}')
        if action:
            Permission.objects.filter(~Q(directory__children='') & ~Q(directory__business__code='NAHAB') & ~Q(permission=256)).delete()
        # for p in Permission.objects.filter(~Q(directory__index_code__code='-1'), ~Q(directory__business__code='NAHAB'), directory__children='', permission=256): #List
        #     if not Permission.objects.filter(directory=p.directory, user=p.user, permission=128).exists(): #Checksum
        #         print(f'{p.user.username} has LIST access on {p.directory.relative_path} without CHECKSUM')
        #         if action:
        #             Permission.objects.create(permission=128, user=p.user, directory=p.directory, created_by=isc_user, is_confirmed=p.is_confirmed)
        for p in Permission.objects.filter(directory__children='', permission=1): #Download
            if not Permission.objects.filter(directory=p.directory, user=p.user, permission=1024).exists(): #Append
                print(f'{p.user.username} has DOWNLOAD access on {p.directory.relative_path} without APPEND')
                if action:
                    Permission.objects.create(permission=1024, user=p.user, directory=p.directory, created_by=isc_user, is_confirmed=p.is_confirmed)
        for p in Permission.objects.filter(directory__children='', permission=4): #Create
            if not Permission.objects.filter(directory=p.directory, user=p.user, permission=0).exists(): #ApplyToSubfolder
                print(f'{p.user.username} has CREATE access on {p.directory.relative_path} without APPLYTOSUBFOLDER')
                if action:
                    Permission.objects.create(permission=0, user=p.user, directory=p.directory, created_by=isc_user, is_confirmed=p.is_confirmed)
        for p in Permission.objects.filter(directory__children='', permission=2): #Upload
            if not Permission.objects.filter(directory=p.directory, user=p.user, permission=512).exists(): #Overwrite
                print(f'{p.user.username} has UPLOAD access on {p.directory.relative_path} without OVERWRITE')
                if action:
                    Permission.objects.create(permission=512, user=p.user, directory=p.directory, created_by=isc_user, is_confirmed=p.is_confirmed)
        for p in Permission.objects.filter(directory__children='', permission=32): #Modify
            if not Permission.objects.filter(directory=p.directory, user=p.user, permission=8).exists(): #RenameFiles
                print(f'{p.user.username} has MODIFY access on {p.directory.relative_path} without RENAME')
                if action:
                    Permission.objects.create(permission=8, user=p.user, directory=p.directory, created_by=isc_user, is_confirmed=p.is_confirmed)
    elif flag == 'mftuser':
        print('Cleanup mftusers.')
        for u in MftUser.objects.all():
            if u.organization.code == 'ISC':
                if '-' not in u.username and '.' in u.username:
                    print(f'mftuser {u.username} corrected')
                    u.username = u.username.replace('.', '_')
                    u.email = f'{u.username}@sita.nibn.net'
                    if action:
                        u.save()
    elif flag == 'dir':
        print('Cleanup directories.')
        for d in Directory.objects.all():
            chs = d.children
            old_chs = chs
            chs = ''
            temp = old_chs.split(',')
            temp.pop()
            for c in temp:
                id_ = int(c)
                # print(f'Checking dir with id {id}')
                if Directory.objects.filter(pk=id_).exists():
                    chs += f'{id_},'
                    recursive_directory_survey(Directory.objects.get(pk=id_), action=action)
                else:
                    print(f'dir with id {id_} does not exists, Parent id is {d.id}')
            d.children = chs
            if action:
                d.save()
    elif flag == 'dir1':
        print('Cleanup directories v1.')
        for d in Directory.objects.all():
            if d.parent != 0:
                if not Directory.objects.filter(pk=d.parent).exists():
                    print(f'directory with id {d.parent} does not exists, parent of {d.id}')
                    d_perms = Permission.objects.filter(directory__id=d.id)
                    parent_perms = Permission.objects.filter(directory__id=d.id)
                    print(f'deleting {d_perms.count()} and {parent_perms.count()} permissions')
                    if action:
                        d.delete()
                        d_perms.delete()
                        parent_perms.delete()
    elif flag == 'dir2':
        print('Cleanup directories v2.')
        for d in Directory.objects.all():
            rp = d.relative_path.split('/')
            if rp[-1] != d.name:
                print(f'directory in {d.absolute_path} has mismatch')
                parent = Directory.objects.get(pk=d.parent)
                d.relative_path = f'{parent.relative_path}/{d.name}'
                if action:
                    d.save()
    elif flag == 'dir3':
        print('Cleanup directories v3.')
        keys = list(kwargs.keys())
        value = kwargs[keys[0]]
        bic_ = BankIdentifierCode.objects.get(code=value)
        print(f'Cleanup directories by {keys[0]}.')
        for d in Directory.objects.filter(name=value):
            print(f'directory in {d.absolute_path} exists')
            parent = Directory.objects.get(pk=d.parent)
            if str(d.id) in parent.children:
                print(f'id {str(d.id)} exists in parent with id {parent.id} children')
                temp = parent.children
                temp.replace(f'{str(d.id),}', '')
                parent.children = temp
                if action:
                    d.delete()
                    parent.save()
                    print(f'directory in {d.absolute_path} has been deleted')
    elif flag == 'inv':
        print('Cleanup invoices.')
        for inv in Invoice.objects.all():
            if not MftUser.objects.filter(pk=inv.mftuser).exists():
                print(f'invoice found with serial {inv.serial_number} for none existing mftuser {inv.mftuser}')


def refactor_directory(operation='', action=False, *args, **kwargs):
    if operation == 'rename':
        dirs = Directory.objects.filter(relative_path__icontains=kwargs['old_name'])
        for d in dirs:
            print(d.relative_path)
            if d.name == kwargs['old_name']:
                d.name = kwargs['new_name']
            d.relative_path = d.relative_path.replace(kwargs['old_name'], kwargs['new_name'])
            if action:
                d.save()


def recursive_directory_survey(directory, action=False):
    chs = directory.children
    old_chs = chs
    chs = ''
    temp = old_chs.split(',')
    temp.pop()
    for c in temp:
        id = int(c)
        # print(f'Checking dir with id {id}')
        if Directory.objects.filter(pk=id).exists():
            chs += f'{id},'
            recursive_directory_survey(Directory.objects.get(pk=id))
        else:
            print(f'dir with id {id} does not exists, Parent id is {directory.id}')
    directory.children = chs
    if action:
        directory.save()