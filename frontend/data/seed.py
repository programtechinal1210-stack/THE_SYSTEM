# data/seed.py
from .arrays import *
from datetime import datetime, timedelta
import random

def initialize_data():
    print("🚀 جاري تهيئة البيانات في المصفوفات...")
    
    global USERS, ORGANIZATIONS, CASES, TASKS, DIRECTIVES, REFERRALS, NOTIFICATIONS, STATISTICS
    
    # مستخدمين
    USERS = [
        {"id": generate_id(), "username": "admin", "password": "admin123", "full_name": "مدير النظام", "email": "admin@goms.gov.sa", "phone": "0500000000", "organization_id": "org-001", "role": "admin", "is_active": True, "created_at": now()},
        {"id": generate_id(), "username": "manager", "password": "manager123", "full_name": "مدير المكتب", "email": "manager@goms.gov.sa", "phone": "0500000001", "organization_id": "org-002", "role": "manager", "is_active": True, "created_at": now()},
        {"id": generate_id(), "username": "reviewer", "password": "reviewer123", "full_name": "مراجع المعاملات", "email": "reviewer@goms.gov.sa", "phone": "0500000002", "organization_id": "org-003", "role": "reviewer", "is_active": True, "created_at": now()},
        {"id": generate_id(), "username": "executor", "password": "executor123", "full_name": "منفذ المهام", "email": "executor@goms.gov.sa", "phone": "0500000003", "organization_id": "org-004", "role": "executor", "is_active": True, "created_at": now()},
        {"id": generate_id(), "username": "secretary", "password": "secretary123", "full_name": "سكرتيرة المكتب", "email": "secretary@goms.gov.sa", "phone": "0500000004", "organization_id": "org-002", "role": "secretary", "is_active": True, "created_at": now()},
        {"id": generate_id(), "username": "followup", "password": "followup123", "full_name": "متابعة المهام", "email": "followup@goms.gov.sa", "phone": "0500000005", "organization_id": "org-005", "role": "followup", "is_active": True, "created_at": now()}
    ]
    print(f"   ✅ تم إنشاء {len(USERS)} مستخدم")
    
    # جهات
    ORGANIZATIONS = [
        {"id": "org-001", "name": "الإدارة العليا", "code": "TOP", "level": 1, "is_active": True},
        {"id": "org-002", "name": "السكرتارية العامة", "code": "SEC", "level": 2, "is_active": True},
        {"id": "org-003", "name": "إدارة المشتريات", "code": "PUR", "level": 2, "is_active": True},
        {"id": "org-004", "name": "إدارة الموارد البشرية", "code": "HR", "level": 2, "is_active": True},
        {"id": "org-005", "name": "إدارة التقنية", "code": "IT", "level": 2, "is_active": True},
        {"id": "org-006", "name": "إدارة المالية", "code": "FIN", "level": 2, "is_active": True},
    ]
    print(f"   ✅ تم إنشاء {len(ORGANIZATIONS)} جهة")
    
    # معاملات
    CASES = []
    subjects = ["طلب تمديد عقد الصيانة", "تقرير الميزانية السنوية", "طلب شراء معدات تقنية", "توجيه بشأن الاجتماع القادم", "طلب إجازة رسمية"]
    for i in range(1, 21):
        CASES.append({
            "id": f"case-{i}",
            "case_number": f"و-{i}-2026",
            "subject": random.choice(subjects),
            "case_type": random.choice(["Incoming", "Outgoing", "Internal"]),
            "status": random.choice(["draft", "pending", "inprogress", "completed", "closed"]),
            "priority": random.choice(["Low", "Normal", "High", "Urgent"]),
            "created_at": now(),
            "transaction_date": today()
        })
    print(f"   ✅ تم إنشاء {len(CASES)} معاملة")
    
    # مهام
    TASKS = []
    task_titles = ["مراجعة طلب الصيانة", "إعداد تقرير الميزانية", "تحديث نظام المعلومات", "إعداد جدول الاجتماعات"]
    for i in range(1, 11):
        TASKS.append({
            "id": f"task-{i}",
            "task_number": f"T{i}-2026",
            "title": random.choice(task_titles),
            "status": random.choice(["new", "inprogress", "under_review", "completed", "cancelled"]),
            "priority": random.choice(["Low", "Normal", "High", "Urgent"]),
            "created_at": now(),
            "due_date": today()
        })
    print(f"   ✅ تم إنشاء {len(TASKS)} مهمة")
    
    # إشعارات
    NOTIFICATIONS = []
    for i in range(1, 6):
        NOTIFICATIONS.append({
            "id": f"notif-{i}",
            "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "title": f"إشعار رقم {i}",
            "content": f"محتوى الإشعار {i}",
            "is_read": False,
            "created_at": now()
        })
    print(f"   ✅ تم إنشاء {len(NOTIFICATIONS)} إشعار")
    
    # إحصائيات
    STATISTICS = {
        "total_users": len(USERS),
        "total_cases": len(CASES),
        "total_tasks": len(TASKS),
        "total_notifications": len(NOTIFICATIONS),
    }
    
    print("🎉 تم تهيئة جميع المصفوفات بنجاح!")
