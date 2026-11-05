# modules/module_auth/views/mfa.py
from django.shortcuts import render, redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException, ForbiddenException


def mfa_view(request):
    """Second-factor step. The backend already issued tokens on /auth/login but
    marked the session mfa_verified=False; only /auth/mfa/challenge,
    /auth/mfa/enroll, /auth/logout and /auth/me are reachable until verified.
    """
    token = request.session.get('access_token')
    if not token:
        return redirect('auth:login')
    if request.session.get('mfa_pending') is False:
        # Already completed earlier in this browser session.
        return redirect('core_home')

    client = ApiClient(token=token)
    error = None

    if request.method == 'POST':
        action = request.POST.get('action', 'challenge')
        if action == 'enroll':
            # Step 1 of enrollment: request a provisioning URI + secret, show it.
            try:
                data = client.post("/auth/mfa/enroll")
                request.session['mfa_enroll_secret'] = data.get('secret', '')
                request.session['mfa_enroll_uri'] = data.get('uri', '')
                return redirect('auth:mfa')
            except (ForbiddenException, UnauthorizedException, ApiException) as exc:
                error = f'تعذر بدء التفعيل: {str(exc)[:120]}'
        else:
            # Step 2: verify a 6-digit code, either completing enrollment or
            # satisfying a login challenge.
            code = (request.POST.get('code') or '').strip()
            was_enrolling = bool(request.session.get('mfa_enroll_secret'))
            try:
                if was_enrolling:
                    client.post("/auth/mfa/verify", {"code": code})
                else:
                    client.post("/auth/mfa/challenge", {"code": code})
                request.session['mfa_pending'] = False
                request.session.pop('mfa_enroll_secret', None)
                request.session.pop('mfa_enroll_uri', None)
                messages.success(request, 'تم التحقق بنجاح؛ مرحبًا بك')
                return redirect('core_home')
            except UnauthorizedException:
                messages.error(request, 'رمز التحقق غير صحيح؛ حاول مجددًا')
            except (ForbiddenException, ApiException) as exc:
                messages.error(request, f'تعذر التحقق: {str(exc)[:120]}')

    context = {
        'title': 'التحقق بخطوتين',
        'enroll_uri': request.session.get('mfa_enroll_uri'),
        'enroll_secret': request.session.get('mfa_enroll_secret'),
        'error': error,
    }
    return render(request, 'auth/mfa.html', context)

