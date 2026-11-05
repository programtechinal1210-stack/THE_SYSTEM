/**
 * audit-data.js - حالة التطبيق والبيانات
 * ============================================================
 */

const AuditState = {
    // التبويب النشط
    activeTab: 'dashboard',

    // بيانات الصفحات
    pagination: {
        logs: { page: 1, totalPages: 1, totalCount: 0 },
        followups: { page: 1, totalPages: 1, totalCount: 0 },
        execution: { page: 1, totalPages: 1, totalCount: 0 },
        anomalies: { page: 1, totalPages: 1, totalCount: 0 },
        alerts: { page: 1, totalPages: 1, totalCount: 0 },
        exports: { page: 1, totalPages: 1, totalCount: 0 }
    },

    // الفلاتر النشطة
    filters: {
        logs: {},
        followups: {},
        execution: {},
        anomalies: {},
        alerts: {},
        exports: {}
    },

    // الإحصائيات
    stats: {
        totalActions: 0,
        uniqueUsers: 0,
        pendingFollowups: 0,
        openAnomalies: 0,
        avgDurationMs: 0,
        totalExports: 0
    },

    // عنصر محدد للحذف
    deleteTarget: {
        endpoint: '',
        name: '',
        callback: null
    },

    // تحميل
    loading: {
        logs: false,
        followups: false,
        execution: false,
        anomalies: false,
        alerts: false,
        exports: false
    },

    /**
     * تعيين صفحة
     */
    setPage(section, page) {
        this.pagination[section].page = page;
    },

    /**
     * تعيين فلاتر
     */
    setFilters(section, filters) {
        this.filters[section] = { ...this.filters[section], ...filters };
    },

    /**
     * إعادة تعيين فلاتر
     */
    resetFilters(section) {
        this.filters[section] = {};
        this.pagination[section].page = 1;
    },

    /**
     * الحصول على query params لقسم
     */
    getQueryParams(section) {
        return {
            ...this.filters[section],
            page: this.pagination[section].page,
            page_size: 20
        };
    }
};

// البيانات النموذجية (للتطوير فقط - تستبدل بـ API حقيقي)
const MockData = {
    logs: [
        { id: 1, actor_name: 'أحمد محمد', action_type: 'UPDATE', entity_type: 'case', module: 'cases', severity: 'info', changes_summary: 'تحديث حالة المعاملة و-124-2026', created_at: '2026-07-16T14:30:00' },
        { id: 2, actor_name: 'سارة علي', action_type: 'CREATE', entity_type: 'user', module: 'users', severity: 'info', changes_summary: 'إنشاء مستخدم جديد: نورا سعيد', created_at: '2026-07-16T13:15:00' },
        { id: 3, actor_name: 'محمد خالد', action_type: 'DELETE', entity_type: 'directive', module: 'execution', severity: 'warning', changes_summary: 'حذف توجيه ت-044-2026', created_at: '2026-07-16T11:00:00' },
        { id: 4, actor_name: 'النظام', action_type: 'DETECT', entity_type: 'anomaly', module: 'audit', severity: 'critical', changes_summary: 'كشف محاولة اقتحام من IP 192.168.1.100', created_at: '2026-07-16T09:30:00' },
        { id: 5, actor_name: 'أحمد محمد', action_type: 'EXPORT', entity_type: 'audit', module: 'audit', severity: 'info', changes_summary: 'تصدير سجل التدقيق بتنسيق PDF', created_at: '2026-07-15T16:45:00' }
    ],
    followups: [
        { id: 'f1', entity_type: 'directive', entity_id: 'ت-045-2026', notes: 'متابعة تنفيذ التوجيه', category: 'URGENT', progress_percentage: 65, is_escalated: false, is_overdue: false, due_date: '2026-07-25', created_at: '2026-07-16T10:00:00' },
        { id: 'f2', entity_type: 'task', entity_id: 'م-001-2026', notes: 'جمع البيانات المالية للربع الثاني', category: 'GENERAL', progress_percentage: 80, is_escalated: false, is_overdue: false, due_date: '2026-07-20', created_at: '2026-07-15T08:00:00' },
        { id: 'f3', entity_type: 'action', entity_id: 'إ-002-2026', notes: 'مراجعة الفواتير المستحقة', category: 'REVIEW', progress_percentage: 100, resolved_at: '2026-07-15T12:00:00', is_escalated: false, due_date: '2026-07-15', created_at: '2026-07-14T09:00:00' }
    ],
    execution: [
        { id: 'e1', entity_type: 'directive', entity_id: 'ت-045-2026', action: 'CREATED', actor_name: 'أحمد محمد', notes: 'إنشاء توجيه جديد', duration_seconds: 2, is_delayed: false, created_at: '2026-07-16T14:30:00' },
        { id: 'e2', entity_type: 'task', entity_id: 'م-001-2026', action: 'COMPLETED', actor_name: 'سارة علي', notes: 'إكمال المهمة بنجاح', duration_seconds: 4, is_delayed: false, created_at: '2026-07-16T13:15:00' },
        { id: 'e3', entity_type: 'action', entity_id: 'إ-002-2026', action: 'UPDATED', actor_name: 'محمد خالد', notes: 'تحديث نسبة التقدم', duration_seconds: 1, is_delayed: true, delay_reason: 'تأخر في استلام البيانات', created_at: '2026-07-16T11:00:00' }
    ]
};

console.log('📊 AuditState & MockData جاهز!');
