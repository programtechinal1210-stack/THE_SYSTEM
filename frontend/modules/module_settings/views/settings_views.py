from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from modules.module_settings.services.settings_service import settings_service

def get_settings_api(request):
    """جلب جميع الإعدادات من API"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # جلب إعدادات النظام
        categories = settings_service.get_categories()
        system_settings = settings_service.get_all_system_settings()
        user_settings = settings_service.get_user_settings()

        return JsonResponse({
            'success': True,
            'categories': categories,
            'system': system_settings,
            'user': user_settings
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def save_settings_api(request):
    """حفظ الإعدادات إلى API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        tab = data.get('tab')
        settings = data.get('settings', {})
        
        results = []
        for key, value in settings.items():
            try:
                result = settings_service.update_system_setting(key, value)
                results.append({'key': key, 'status': 'saved', 'value': value})
            except Exception as e:
                results.append({'key': key, 'status': 'error', 'error': str(e)})
        
        return JsonResponse({
            'success': all(item['status'] == 'saved' for item in results),
            'tab': tab,
            'results': results
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def save_user_settings_api(request):
    """حفظ إعدادات المستخدم"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        settings = data.get('settings', {})
        
        results = []
        for key, value in settings.items():
            try:
                result = settings_service.update_user_setting(key, value)
                results.append({'key': key, 'status': 'saved'})
            except Exception as e:
                results.append({'key': key, 'status': 'error', 'error': str(e)})
        
        return JsonResponse({'success': all(item['status'] == 'saved' for item in results), 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def change_password_api(request):
    """تغيير كلمة المرور"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return JsonResponse({'success': False, 'error': 'كلمة المرور مطلوبة'}, status=400)
        
        result = settings_service.change_password(current_password, new_password)
        request.session.flush()
        return JsonResponse({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
