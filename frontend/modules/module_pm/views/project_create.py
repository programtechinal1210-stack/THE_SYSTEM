from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from shared.services.api_client import (
    ApiClient,
    ApiException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from .planning import allowed


@require_GET
def next_project_code(request):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        client.get('/pm/')
        identity = client.get('/auth/me')
        if not allowed(identity, 'pm.projects.create'):
            return JsonResponse({'detail': 'ليس لديك صلاحية إنشاء مشروع'}, status=403)
        return JsonResponse(client.get('/pm/projects/next-code'))
    except UnauthorizedException:
        return JsonResponse({'detail': 'انتهت جلسة الدخول'}, status=401)
    except ForbiddenException:
        return JsonResponse({'detail': 'ليس لديك صلاحية إنشاء مشروع'}, status=403)
    except NotFoundException:
        return JsonResponse({'detail': 'خدمة إنشاء المشاريع غير متاحة'}, status=404)
    except ApiException:
        return JsonResponse({'detail': 'تعذر توليد رمز المشروع'}, status=503)


def form_context(values, references, error=None):
    currencies = references.get('currencies', [])
    currency = values.get('currency') or next(
        (item['id'] for item in currencies if item['id'] == 'YER'),
        currencies[0]['id'] if currencies else '',
    )
    return {
        'values': {
            'project_code': values.get('project_code', ''),
            'name': values.get('name', ''),
            'project_manager_user_id': values.get('project_manager_user_id', ''),
            'directive_date': values.get('directive_date') or str(timezone.localdate()),
            'organization_id': values.get('organization_id', ''),
            'client_name': values.get('client_name', ''),
            'start_date': values.get('start_date') or values.get('directive_date') or str(timezone.localdate()),
            'currency': currency,
            'daily_hours': values.get('daily_hours') or '8',
        },
        'organizations': references.get('organizations', []),
        'managers': references.get('managers', []),
        'currencies': currencies,
        'error': error,
    }


@require_http_methods(['GET', 'POST'])
def create_project(request):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        client.get('/pm/')
        identity = client.get('/auth/me')
        request.core_identity = identity
        request.core_modules = client.get('/modules')
        if not allowed(identity, 'pm.projects.create'):
            return HttpResponse('ليس لديك صلاحية إنشاء مشروع', status=403)

        references = client.get('/pm/planning-references', params={'action': 'create'})
        values = {
            key: request.POST.get(key, '')
            for key in (
                'project_code',
                'name',
                'project_manager_user_id',
                'directive_date',
                'organization_id',
                'client_name',
                'start_date',
                'currency',
                'daily_hours',
            )
        } if request.method == 'POST' else {}
        if request.method == 'POST':
            if not values['start_date']:
                values['start_date'] = values['directive_date']
            try:
                project = client.post('/pm/projects', data=values)
                messages.success(request, 'تم إنشاء المشروع بنجاح.')
                return redirect('/pm/projects/')
            except (ForbiddenException, NotFoundException, UnauthorizedException):
                raise
            except ValidationException:
                context = form_context(
                    values,
                    references,
                    'تحقق من الحقول المطلوبة والتواريخ وصحة الجهة ومدير المشروع والعملة.',
                )
            except ApiException as exc:
                if 'Business code already exists' in str(exc):
                    values['project_code'] = client.get('/pm/projects/next-code')['project_code']
                    message = 'الرمز السابق مستخدم بالفعل؛ حدّثنا الرمز تلقائياً، راجع البيانات ثم أعد المحاولة.'
                else:
                    message = 'تعذر حفظ المشروع. تحقق من رمز المشروع والجهة ومدير المشروع، ثم أعد المحاولة.'
                context = form_context(values, references, message)
        else:
            values['project_code'] = client.get('/pm/projects/next-code')['project_code']
            context = form_context(values, references)
        return render(request, 'pm/project_create.html', {
            'page_title': 'إنشاء مشروع جديد',
            **context,
        })
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية إنشاء مشروع', status=403)
    except NotFoundException:
        return HttpResponse('وحدة إدارة المشاريع أو مراجعها غير متاحة', status=404)
    except ApiException:
        return HttpResponse('تعذر تحميل نموذج إنشاء المشروع؛ حاول مجددًا', status=503)
