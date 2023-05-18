from django import forms
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import *


class AddBusinessForm(forms.ModelForm):
    code        = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "کد پروژه", "class": "form-control"}))
    description = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "نام کامل (فارسی)", "class": "form-control"}))
    address     = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "/DATA", "class": "form-control"}))

    class Meta:
        model = BusinessCode
        fields = [
            'code',
            'description',
            'address',
        ]
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if BusinessCode.objects.filter(code=code).exists():
            raise ValidationError('کد پروژه/سامانه وارد شده تکراری می باشد.')
        return code


class MftUserForm(forms.ModelForm):
    username     = forms.CharField(max_length=101, required=True, label='username', error_messages={'required': 'تمام فیلدهای ستاره دار را تکمیل نمائید'}, widget=forms.TextInput(attrs={"placeholder": "به صورت خودکار تکمیل می گردد", "class": "form-control", "readonly": "readonly"}))
    alias        = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"placeholder": "برای استفاده به صورت سیستمی", "class": "form-control"}))
    firstname    = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "First Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    lastname     = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "Last Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    email        = forms.EmailField(max_length=120, required=True, error_messages={'required': 'تمام فیلدهای ستاره دار را تکمیل نمائید'}, widget=forms.EmailInput(attrs={"placeholder": "username@mail.com", "class": "form-control"}))
    officephone  = forms.DecimalField(max_digits=8, required=True, widget=forms.TextInput(attrs={"placeholder": "123456798", "maxlength": "8", "class": "form-control"}))
    mobilephone  = forms.DecimalField(max_digits=11, required=True, widget=forms.TextInput(attrs={"placeholder": "09123456798", "maxlength": "11", "class": "form-control"}))
    organization = forms.ChoiceField(required=True, error_messages={'invalid_choice': 'یک سازمان/بانک را انتخاب نمائید'}, widget=forms.Select(attrs={"class": "form-control form-select form-select-bg-left", "parent": "organization"}))
    business     = forms.MultipleChoiceField(required=True, widget=forms.SelectMultiple(attrs={"style": "direction: rtl", "class": "form-control form-select", "size": 10, "parent": "business", "data-search": "true", "data-silent-initial-value-set": "true"}))
    # business     = forms.MultipleChoiceField(required=True, widget=forms.CheckboxSelectMultiple(attrs={"style": "direction: rtl", "class": "form-control form-check", "parent": "business", "data-search": "true", "data-silent-initial-value-set": "true"}))
    # ipaddr       = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={"placeholder": "123.123.123.123", "class": "form-control"}))
    # disk_quota   = forms.IntegerField(max_value=100000000, min_value=100, help_text='کمک کمک کمک', required=True, widget=forms.TextInput(attrs={"placeholder": "حجم مورد نیاز در سیتا", "class": "form-control"}))
    # description  = forms.CharField(max_length=250, required=True, widget=forms.Textarea(attrs={"name": "description", "rows":"5", "placeholder": "نام گروه کاربر در شرکت خدمات یا نام اداره، قسمت و یا ... کاربر در بانک، سازمان و ...", "class": "form-control"}))
    
    class Meta:
        model = MftUser
        fields = [
            'username',
            'alias',
            'firstname',
            'lastname',
            'email',
            'officephone',
            'mobilephone',
            'organization',
            'business',
        ]
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(MftUserForm, self).__init__(*args, **kwargs)

    # def clean_username(self):
    #     username = self.cleaned_data.get('username')
    #     if username == '':
    #         print('username is empty')
    #         raise ValidationError('تکمیل فیلدهای ستاره دار الزامی می باشد.')
    #     return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email == '':
            raise ValidationError('تکمیل فیلدهای ستاره دار الزامی می باشد.')
        if '@' not in email:
            raise ValidationError('آدرس ایمیل وارد شده صحیح نیست.')
        if MftUser.objects.filter(email=email).exists():
            if 'create' not in self.request.path:
                id_ = int(self.request.path.split('/')[-2])
                mftuser = MftUser.objects.get(pk=id_)
                temp_user = MftUser.objects.get(email=email)
                if mftuser != temp_user:
                    raise ValidationError('این آدرس ایمیل قبلاً برای کاربری دیگر استفاده شده است.')
            else:
                raise ValidationError('کاربری با این آدرس ایمیل قبلاً ثبت شده است.')
        return email
    
    def clean_alias(self):
        alias = self.cleaned_data.get('alias')
        if alias != '':
            if MftUser.objects.filter(Q(alias=alias) | Q(username=alias)).exists():
                if 'create' not in self.request.path:
                    id_ = int(self.request.path.split('/')[-2])
                    mftuser = MftUser.objects.get(pk=id_)
                    temp_user = MftUser.objects.get(alias=alias)
                    if mftuser != temp_user:
                        raise ValidationError('این نام مستعار قبلاً برای کاربری دیگر استفاده شده است.')
                else:
                    raise ValidationError('نام مستعار انتخاب شده تکراری می باشد.')
            if alias == self.cleaned_data.get('username'):
                raise ValidationError('نام مستعار نمی تواند برابر نام کاربری باشد.')
        return alias
    
    def clean_organization(self):
        org = BankIdentifierCode.objects.get(pk=self.cleaned_data.get('organization'))
        return org
    
    # def clean_business(self):
    #     business = BusinessCode.objects.get(id=self.cleaned_data.get('business'))
    #     return business
    
    def clean_mobilephone(self):
        phone_number = str(self.cleaned_data.get('mobilephone'))
        if MftUser.objects.filter(mobilephone=phone_number).exists():
            # raise ValidationError
            if 'create' in self.request.path:
                self.add_error(self.fields['username'].label, 'کاربری با این مشخصات در سامانه موجود می باشد.')
            else:
                id_ = int(self.request.path.split('/')[-2])
                mftuser = MftUser.objects.get(pk=id_)
                temp_user = MftUser.objects.get(mobilephone=phone_number)
                if mftuser != temp_user:
                    raise ValidationError('این شماره همراه قبلاً برای کاربر دیگری استفاده شده است.')
        if not phone_number.startswith('9'):
            raise ValidationError('یک شماره همراه صحیح وارد کنید.')
        if len(phone_number) < 10 or len(phone_number) > 10:
            raise ValidationError('شماره همراه وارد شده صحیح نیست.')
        return phone_number
    
    def clean_officephone(self):
        phone_number = str(self.cleaned_data.get('officephone'))
        if len(phone_number) < 8 or len(phone_number) > 8:
            raise ValidationError('شماره همراه وارد شده صحیح نیست.')
        return phone_number
    
    # def clean_ipaddr(self):
    #     ip = str(self.cleaned_data.get('ipaddr'))
    #     if ip == '':
    #         return ''
    #     if len(ip) < 7:
    #         raise ValidationError('آدرس آی پی وارد شده صحیح نیست.')
    #     if len(ip.split('.')) < 4:
    #         raise ValidationError('آدرس آی پی وارد شده صحیح نیست.')
    #     if '..' in ip or '...' in ip:
    #         raise ValidationError('آدرس آی پی وارد شده صحیح نیست.')
    #     if ip.startswith('.') or ip.endswith('.'):
    #         raise ValidationError('آدرس آی پی وارد شده صحیح نیست.')
    #     return ip


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Username", "class": "form-control"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"}))


class ChangePasswordForm(forms.Form):
    old_password    = forms.CharField(max_length=100, required=True, widget=forms.PasswordInput(attrs={"placeholder": "Old Password", "class": "form-control"}))
    new_password    = forms.CharField(max_length=100, required=True, widget=forms.PasswordInput(attrs={"placeholder": "New Password", "class": "form-control"}))
    repeat_password = forms.CharField(max_length=100, required=True, widget=forms.PasswordInput(attrs={"placeholder": "Repeat Password", "class": "form-control"}))


class IscUserForm(forms.ModelForm):
    username     = forms.CharField(max_length=101, required=True, widget=forms.TextInput(attrs={"placeholder": "Username", "class": "form-control"}))
    password     = forms.CharField(min_length=8, required=True, widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"}))
    firstname    = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "First Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    lastname     = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "Last Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    email        = forms.EmailField(max_length=120, required=True, widget=forms.EmailInput(attrs={"placeholder": "username@isc.co.ir", "class": "form-control"}))
    officephone  = forms.DecimalField(max_digits=8, required=True, widget=forms.TextInput(attrs={"placeholder": "123456798", "maxlength": "8", "class": "form-control"}))
    mobilephone  = forms.DecimalField(max_digits=11, required=True, widget=forms.TextInput(attrs={"placeholder": "09123456798", "maxlength": "11", "class": "form-control"}))
    department   = forms.ChoiceField(required=True, widget=forms.Select(attrs={"class": "form-control form-select", "parent": "department"}))
    business     = forms.MultipleChoiceField(required=True, widget=forms.SelectMultiple(attrs={"class": "form-control form-select", "parent": "business"}))
    
    class Meta:
        model = IscUser
        fields = [
            'username',
            'password',
            'firstname',
            'lastname',
            'email',
            'officephone',
            'mobilephone',
            'department',
            'business',
        ]
    
    def clean_department(self):
        dept = IscDepartmentCode.objects.get(id=self.cleaned_data.get('department'))
        return dept
    
    # def clean_business(self):
    #     business = BusinessCode.objects.get(id=self.cleaned_data.get('business'))
    #     return business
    
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
        if User.objects.filter(username=username).exists():
            raise ValidationError('کاربر با این نام کاربری وجود دارد')
        if '_' not in username:
            raise ValidationError('فرمت نام کاربری صحیح نیست')
        return username


class UserProfileForm(forms.Form):
    username     = forms.CharField(max_length=101, required=True, widget=forms.TextInput(attrs={"placeholder": "Username", "class": "form-control"}))
    # password     = forms.CharField(min_length=8, required=True, widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"}))
    firstname    = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "First Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    lastname     = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={"placeholder": "Last Name", "class": "form-control", "pattern": "[a-zA-Z].+"}))
    email        = forms.EmailField(max_length=120, required=True, widget=forms.EmailInput(attrs={"placeholder": "username@isc.co.ir", "class": "form-control"}))
    officephone  = forms.DecimalField(max_digits=8, required=True, widget=forms.TextInput(attrs={"placeholder": "123456798", "maxlength": "8", "class": "form-control"}))
    mobilephone  = forms.DecimalField(max_digits=11, required=True, widget=forms.TextInput(attrs={"placeholder": "09123456798", "maxlength": "11", "class": "form-control"}))
    department   = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"style": "direction: rlt", "placeholder": "Department", "class": "form-control", "readonly": "true"}))
    # business     = forms.ChoiceField(required=True, widget=forms.Select(attrs={"style": "direction: rtl", "class": "form-control form-select", "parent": "business"}))
    
    class Meta:
        # model = IscUser
        fields = [
            'username',
            # 'password',
            'firstname',
            'lastname',
            'email',
            'officephone',
            'mobilephone',
            'department',
            # 'business',
        ]
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserProfileForm, self).__init__(*args, **kwargs)
    
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
        if User.objects.filter(username=username).exists() and username != self.request.user.username:
            raise ValidationError('کاربر با این نام کاربری وجود دارد')
        if '_' not in username:
            raise ValidationError('فرمت نام کاربری صحیح نیست')
        return username


class BusinessSelectionForm(forms.Form):
    owned_business = forms.MultipleChoiceField(required=True, widget=forms.SelectMultiple(attrs={"style": "direction: rtl", "class": "form-control form-select", "size": 20, "parent": "owned-business"}))
    used_business  = forms.MultipleChoiceField(required=False, widget=forms.SelectMultiple(attrs={"style": "direction: rtl", "class": "form-control form-select", "size": 20, "parent": "used-business"}))
    
    class Meta:
        fields = (
            'owned_business',
            'used_business'
        )