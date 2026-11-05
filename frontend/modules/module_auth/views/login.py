# modules/module_auth/views/login.py
from django.shortcuts import render, redirect
from django.contrib import messages
from ..forms import LoginForm
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException

def login_view(request):
    # إذا كان المستخدم مسجل دخوله مسبقاً
    if request.session.get('is_authenticated') and request.session.get('access_token'):
        return redirect('core_home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            # ⭐ استدعاء مباشر للـ API بدلاً من auth_api الوسيط
            client = ApiClient()
            client.timeout = 5  # timeout قصير لتسجيل الدخول
            
            try:
                response = client.post(
                    "/auth/login",
                    data={"username": username, "password": password},
                    include_auth=False
                )
                
                access_token = response.get('access_token')
                user_data = response.get('user', response)
                mfa_required = bool(response.get('mfa_required'))

                # تخزين في session
                request.session.cycle_key()
                request.session['refresh_token'] = response.get('refresh_token', '')
                request.session['access_token'] = access_token
                request.session['user_id'] = user_data.get('user_id', user_data.get('user_id', user_data.get('id', '')))
                request.session['username'] = user_data.get('username', username)
                request.session['full_name'] = user_data.get('full_name', username)
                request.session['is_authenticated'] = True

                # تخزين في cache

                request.session['show_welcome'] = True
                if mfa_required:
                    # Backend flagged this session as pending second-factor verification.
                    request.session['mfa_pending'] = True
                    return redirect('auth:mfa')
                request.session['mfa_pending'] = False
                return redirect('core_home')
                
            except UnauthorizedException:
                messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
            except ApiException as e:
                messages.error(request, f'فشل الاتصال: {str(e)[:100]}')
            except Exception as e:
                messages.error(request, f'حدث خطأ غير متوقع')
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form, 'title': 'تسجيل الدخول'})
