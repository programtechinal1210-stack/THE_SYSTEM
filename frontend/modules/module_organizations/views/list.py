# modules/module_organizations/views/list.py
from django.shortcuts import render

def organizations_list(request):
    """عرض صفحة إدارة الجهات"""
    return render(request, 'organizations/index.html', {
        'page_title': 'الجهات',
        'active': 'organizations'
    })
