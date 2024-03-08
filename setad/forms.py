from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError

from core.models import IscDepartmentCode, BusinessCode

from .models import *


class SetadUserForm(forms.ModelForm):
    username     = forms.CharField(max_length=101, required=True, widget=forms.TextInput(attrs={"placeholder": "username@iranet.net or username@amaliat.local", "class": "form-control"}))
    firstname    = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "First Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    lastname     = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "Last Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    email        = forms.EmailField(max_length=120, required=True, widget=forms.EmailInput(attrs={"placeholder": "username@isc.co.ir", "class": "form-control"}))
    officephone  = forms.DecimalField(max_digits=8, required=True, widget=forms.TextInput(attrs={"placeholder": "123456798", "maxlength": "8", "class": "form-control"}))
    mobilephone  = forms.DecimalField(max_digits=11, required=True, widget=forms.TextInput(attrs={"placeholder": "09123456798", "maxlength": "11", "class": "form-control"}))
    department   = forms.ChoiceField(required=True, widget=forms.Select(attrs={"class": "form-control form-select", "parent": "department"}))
    business     = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"size": 10, "parent": "business"}))
    
    class Meta:
        model = SetadUserInvoice
        fields = [
            'username',
            'firstname',
            'lastname',
            'email',
            'officephone',
            'mobilephone',
            'department',
            'business'
        ]

    def clean_department(self):
        dept = IscDepartmentCode.objects.get(id=self.cleaned_data.get('department'))
        return dept
    
    def clean_business(self):
        business = self.cleaned_data.get('business')
        # for bus in self.cleaned_data.get('business'):
        #     business += f'{bus},'
        if not business or business == []:
            raise ValidationError('باید حداقل یک پروژه/سامانه انتخاب کنید.')
        return business
    
    def clean_mobilephone(self):
        phone_number = str(self.cleaned_data.get('mobilephone'))
        if not phone_number.startswith('9'):
            raise ValidationError('یک شماره همراه صحیح وارد کنید.')
        if len(phone_number) < 10 or len(phone_number) > 10:
            raise ValidationError('شماره همراه وارد شده صحیح نیست.')
        return phone_number
    
    def clean_officephone(self):
        phone_number = str(self.cleaned_data.get('officephone'))
        if len(phone_number) < 8 or len(phone_number) > 8:
            raise ValidationError('شماره وارد شده صحیح نیست.')
        return phone_number
    
    def clean_username(self):
        username = str(self.cleaned_data.get('username'))
        if '_' not in username:
            raise ValidationError('فرمت نام کاربری صحیح نیست')
        return username
    
    def clean_email(self):
        email = str(self.cleaned_data.get('email'))
        if '_' not in email and '@' not in email:
            raise ValidationError('فرمت ایمیل صحیح نیست')
        return email

