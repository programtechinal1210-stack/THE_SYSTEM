# ============================================================
# مصفوفات البيانات - Mock Data (الكاملة)
# ============================================================

from datetime import datetime
import uuid

# ===== مصفوفة المهام =====
TASKS_DATA = [
    {"id": 1, "number": "م-001-2026", "title": "مراجعة عروض المعدات المكتبية", "priority": "عاجل", 
     "status": "قيد التنفيذ", "assignee": "أحمد محمد", "progress": 65, "dueDate": "2026-01-22", "overdue": True},
    {"id": 2, "number": "م-002-2026", "title": "إعداد تقرير التوصية النهائي", "priority": "عالية", 
     "status": "قيد التنفيذ", "assignee": "سارة علي", "progress": 80, "dueDate": "2026-02-01", "overdue": False},
    {"id": 3, "number": "م-003-2026", "title": "مراجعة طلب التوظيف", "priority": "عادية", 
     "status": "مكتمل", "assignee": "محمد خالد", "progress": 100, "dueDate": "2026-01-15", "overdue": False},
    {"id": 4, "number": "م-004-2026", "title": "تحليل بيانات الأداء الربع سنوي", "priority": "عادية", 
     "status": "جديد", "assignee": "نورا سعيد", "progress": 0, "dueDate": "2026-02-10", "overdue": False},
    {"id": 5, "number": "م-005-2026", "title": "اعتماد الميزانية السنوية", "priority": "عاجل", 
     "status": "معلق", "assignee": "مدير الإدارة", "progress": 45, "dueDate": "2026-01-10", "overdue": True},
]

# ===== مصفوفة المعاملات =====
CASES_DATA = [
    {"id": 1, "number": "و-124-2026", "subject": "طلب توريد معدات مكتبية", "type": "وارد", 
     "priority": "عاجل", "status": "قيد المراجعة", "date": "2026-01-20", "overdue": False},
    {"id": 2, "number": "ص-89-2026", "subject": "خطاب رسمي للجهات الحكومية", "type": "صادر", 
     "priority": "عادية", "status": "مكتمل", "date": "2026-01-19", "overdue": False},
    {"id": 3, "number": "د-45-2026", "subject": "توجيه إداري عاجل بشأن المشروع", "type": "داخلي", 
     "priority": "عاجل", "status": "متأخر", "date": "2026-01-15", "overdue": True},
]

# ===== مصفوفة المستخدمين =====
USERS_DATA = [
    {"id": 1, "username": "ahmed.mohamed", "email": "ahmed@domain.com", "role": "مدير", "status": "نشط", "date": "2026-01-15"},
    {"id": 2, "username": "sara.ali", "email": "sara@domain.com", "role": "مشرف", "status": "نشط", "date": "2026-01-20"},
    {"id": 3, "username": "khaled.ahmed", "email": "khaled@domain.com", "role": "مستخدم", "status": "غير نشط", "date": "2026-02-01"},
]

# ===== مصفوفة الجهات =====
ORGANIZATIONS_DATA = [
    {"id": 1, "name": "الإدارة العليا", "code": "TOP", "type": "داخلية", "parent": None, 
     "email": "top@domain.com", "phone": "0501111111", "address": "الرياض - المملكة العربية السعودية", "status": "نشطة"},
    {"id": 2, "name": "السكرتارية العامة", "code": "SEC", "type": "داخلية", "parent": "الإدارة العليا", 
     "email": "sec@domain.com", "phone": "0502222222", "address": "الرياض - المملكة العربية السعودية", "status": "نشطة"},
    {"id": 3, "name": "إدارة المشتريات", "code": "PUR", "type": "داخلية", "parent": "الإدارة العليا", 
     "email": "pur@domain.com", "phone": "0503333333", "address": "الرياض - المملكة العربية السعودية", "status": "نشطة"},
    {"id": 4, "name": "إدارة الموارد البشرية", "code": "HR", "type": "داخلية", "parent": "الإدارة العليا", 
     "email": "hr@domain.com", "phone": "0504444444", "address": "الرياض - المملكة العربية السعودية", "status": "نشطة"},
    {"id": 5, "name": "إدارة التقنية", "code": "IT", "type": "داخلية", "parent": "الإدارة العليا", 
     "email": "it@domain.com", "phone": "0505555555", "address": "الرياض - المملكة العربية السعودية", "status": "غير نشطة"},
]

# ===== مصفوفة الإشعارات =====
NOTIFICATIONS_DATA = [
    {"id": 1, "user_id": 1, "title": "مهمة جديدة", "message": "تم إضافة مهمة جديدة لك", "type": "info", "read": False, "date": "2026-01-20"},
    {"id": 2, "user_id": 2, "title": "تحديث حالة", "message": "تم تحديث حالة المهمة", "type": "warning", "read": False, "date": "2026-01-19"},
    {"id": 3, "user_id": 3, "title": "إشعار مهم", "message": "لديك 3 مهام متأخرة", "type": "danger", "read": False, "date": "2026-01-18"},
]

# ===== مصفوفة التوجيهات =====
DIRECTIVES_DATA = [
    {"id": 1, "number": "ت-001-2026", "title": "توجيه بشأن المشتريات", "status": "نشط", "priority": "عادي", 
     "source": "الإدارة العليا", "target": "إدارة المشتريات", "date": "2026-01-20"},
    {"id": 2, "number": "ت-002-2026", "title": "توجيه لتحديث النظام", "status": "قيد التنفيذ", "priority": "عاجل", 
     "source": "الإدارة العليا", "target": "إدارة التقنية", "date": "2026-01-18"},
]

# ===== مصفوفة الإحالات =====
REFERRALS_DATA = [
    {"id": 1, "case_id": 1, "from_user": "أحمد محمد", "to_user": "سارة علي", 
     "instructions": "مراجعة الطلب وإبداء الرأي", "status": "قيد المراجعة", "date": "2026-01-20"},
    {"id": 2, "case_id": 2, "from_user": "سارة علي", "to_user": "محمد خالد", 
     "instructions": "التأكيد على الإجراءات المطلوبة", "status": "مكتمل", "date": "2026-01-19"},
]

# ===== مصفوفة التقارير =====
REPORTS_DATA = []

# ===== إحصائيات النظام =====
STATISTICS = {
    "total_tasks": len(TASKS_DATA),
    "total_cases": len(CASES_DATA),
    "total_users": len(USERS_DATA),
    "total_organizations": len(ORGANIZATIONS_DATA),
    "total_directives": len(DIRECTIVES_DATA),
    "total_referrals": len(REFERRALS_DATA),
    "pending_tasks": len([t for t in TASKS_DATA if t["status"] == "جديد"]),
    "completed_tasks": len([t for t in TASKS_DATA if t["status"] == "مكتمل"]),
    "overdue_tasks": len([t for t in TASKS_DATA if t["overdue"]]),
    "active_cases": len([c for c in CASES_DATA if c["status"] not in ["مكتمل", "مغلقة"]]),
}

# ===================================================================
# دوال مساعدة للبحث عن البيانات
# ===================================================================

def get_user_by_id(user_id):
    """البحث عن مستخدم بواسطة المعرف"""
    for user in USERS_DATA:
        if user["id"] == user_id:
            return user
    return None

def get_user_by_username(username):
    """البحث عن مستخدم بواسطة اسم المستخدم"""
    for user in USERS_DATA:
        if user["username"] == username:
            return user
    return None

def get_task_by_id(task_id):
    """البحث عن مهمة بواسطة المعرف"""
    for task in TASKS_DATA:
        if task["id"] == task_id:
            return task
    return None

def get_case_by_id(case_id):
    """البحث عن معاملة بواسطة المعرف"""
    for case in CASES_DATA:
        if case["id"] == case_id:
            return case
    return None

def get_organization_by_id(org_id):
    """البحث عن جهة بواسطة المعرف"""
    for org in ORGANIZATIONS_DATA:
        if org["id"] == org_id:
            return org
    return None

def get_directive_by_id(dir_id):
    """البحث عن توجيه بواسطة المعرف"""
    for directive in DIRECTIVES_DATA:
        if directive["id"] == dir_id:
            return directive
    return None

def get_referral_by_id(ref_id):
    """البحث عن إحالة بواسطة المعرف"""
    for referral in REFERRALS_DATA:
        if referral["id"] == ref_id:
            return referral
    return None

def get_notification_by_id(notif_id):
    """البحث عن إشعار بواسطة المعرف"""
    for notification in NOTIFICATIONS_DATA:
        if notification["id"] == notif_id:
            return notification
    return None

# ===================================================================
# دوال مساعدة عامة
# ===================================================================

def generate_id():
    """توليد معرف فريد (رقمي)"""
    import random
    return random.randint(1000, 9999)

def now():
    """الحصول على الوقت الحالي بصيغة نصية"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_tasks():
    return TASKS_DATA

def get_cases():
    return CASES_DATA

def get_users():
    return USERS_DATA

def get_organizations():
    return ORGANIZATIONS_DATA

def get_notifications():
    return NOTIFICATIONS_DATA

def get_directives():
    return DIRECTIVES_DATA

def get_referrals():
    return REFERRALS_DATA

# ===================================================================
# مرادفات للاستيراد المباشر (لتسهيل الاستخدام في الوحدات)
# ===================================================================

TASKS = TASKS_DATA
CASES = CASES_DATA
USERS = USERS_DATA
ORGANIZATIONS = ORGANIZATIONS_DATA
NOTIFICATIONS = NOTIFICATIONS_DATA
DIRECTIVES = DIRECTIVES_DATA
REFERRALS = REFERRALS_DATA
REPORTS = REPORTS_DATA