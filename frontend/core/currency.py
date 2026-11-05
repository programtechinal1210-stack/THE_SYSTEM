"""Currency workspace over the existing Core currency API."""
from datetime import date
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException, ForbiddenException


@require_http_methods(['GET', 'POST'])
def page(request):
    client = ApiClient(token=request.session.get('access_token'))
    context = {'page_title':'العملات وأسعار الصرف', 'today':date.today().isoformat(),
               'values':request.POST, 'error':None}
    try:
        identity = client.get('/auth/me')
        request.core_identity = identity
        request.core_modules = client.get('/modules')
        permissions = identity.get('permissions', [])
        if not identity.get('is_admin') and 'core.currency.view' not in permissions:
            return HttpResponse('ليس لديك صلاحية عرض العملات', status=403)
        context['can_manage'] = identity.get('is_admin') or 'core.currency.manage' in permissions
        if request.method == 'POST':
            if not context['can_manage']:
                return HttpResponse('ليس لديك صلاحية إدارة العملات', status=403)
            try:
                command = request.POST.get('command')
                if command == 'currency':
                    client.post('/currency/currencies', data={
                        'code':request.POST.get('code','').strip().upper(),
                        'name':request.POST.get('name','').strip(),
                        'symbol':request.POST.get('symbol','').strip(), 'is_anchor':False})
                elif command == 'rate':
                    client.post('/currency/rates', data={
                        'from_currency':request.POST.get('currency',''), 'to_currency':'YER',
                        'rate':request.POST.get('rate',''), 'effective_date':request.POST.get('effective_date',''),
                        'source':'user_sale_rate'})
                else:
                    return HttpResponse('عملية غير صالحة', status=400)
                return redirect('/currency/')
            except (UnauthorizedException, ForbiddenException):
                raise
            except ApiException:
                context['error']='تعذر الحفظ. تحقق من الرمز وتفرده، وسعر موجب، وتاريخ صحيح. لا تُعدّل الأسعار القديمة؛ أضف سعرًا جديدًا بتاريخ سريانه.'
        currencies = client.get('/currency/currencies')
        lookup = {c['id']:c for c in currencies}
        context['currencies'] = currencies
        context['foreign_currencies'] = [c for c in currencies if c['code']!='YER']
        rates = client.get('/currency/rates')
        for row in rates:
            row['from_label'] = lookup.get(row['from_currency'],{}).get('code',row['from_currency'])
            row['to_label'] = lookup.get(row['to_currency'],{}).get('code',row['to_currency'])
        context['rates'] = rates
        return render(request,'core/currency.html',context,status=400 if context['error'] else 200)
    except UnauthorizedException:
        return redirect('/auth/login/')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية لهذه العملية',status=403)
    except ApiException:
        return HttpResponse('تعذر الاتصال بخدمة العملات. حاول مجددًا.',status=503)
