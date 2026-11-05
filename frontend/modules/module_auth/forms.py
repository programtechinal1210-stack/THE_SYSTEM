from django import forms

class LoginForm(forms.Form):
    username = forms.CharField(label='اسم المستخدم', max_length=150, widget=forms.TextInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل اسم المستخدم', 'autofocus': True}))
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل كلمة المرور'}))
    remember_me = forms.BooleanField(label='تذكرني', required=False, widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}))

class RegisterForm(forms.Form):
    username = forms.CharField(label='اسم المستخدم', max_length=150, widget=forms.TextInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل اسم المستخدم'}))
    email = forms.EmailField(label='البريد الإلكتروني', widget=forms.EmailInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل البريد الإلكتروني'}))
    password = forms.CharField(label='كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل كلمة المرور'}))
    confirm_password = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-input w-full', 'placeholder': 'أعد إدخال كلمة المرور'}))
    full_name = forms.CharField(label='الاسم الكامل', max_length=255, required=False, widget=forms.TextInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل الاسم الكامل'}))

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label='البريد الإلكتروني', widget=forms.EmailInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل البريد الإلكتروني'}))

class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(label='كلمة المرور الجديدة', widget=forms.PasswordInput(attrs={'class': 'form-input w-full', 'placeholder': 'أدخل كلمة المرور الجديدة'}))
    confirm_password = forms.CharField(label='تأكيد كلمة المرور', widget=forms.PasswordInput(attrs={'class': 'form-input w-full', 'placeholder': 'أعد إدخال كلمة المرور'}))
