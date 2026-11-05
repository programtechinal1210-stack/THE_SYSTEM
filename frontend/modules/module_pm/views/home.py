from uuid import UUID
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from ..services.operations import SECTIONS
from ..services.planning import allowed
from shared.services.api_client import (
    ApiClient, ApiException, ForbiddenException, NotFoundException, UnauthorizedException,
)

PROJECT_STATUSES = (
    ("issued", "صادر التوجيه"),
    ("planning", "قيد التخطيط"),
    ("planned", "تم التخطيط"),
    ("in_progress", "قيد التنفيذ"),
    ("completed", "مكتمل"),
)


def portfolio_context(items):
    status_labels = dict(PROJECT_STATUSES)
    status_counts = {status: 0 for status, _ in PROJECT_STATUSES}
    open_risks = 0
    open_deviations = 0
    project_rows = []
    for item in items:
        status = item["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        open_risks += int(item["open_risks"])
        open_deviations += int(item["open_deviations"])
        project_rows.append({
            **item,
            "status_label": status_labels.get(status, status),
            "href": f'/pm/projects/{UUID(item["project_id"])}/reporting/',
        })

    budgets = {}
    for item in items:
        currency = item['currency']
        budgets[currency] = budgets.get(currency, Decimal('0')) + Decimal(item['planned_cost'])
    next_actions = {
        "issued": ("بدء التخطيط", "ابدأ تخطيط المشروع واعتماد مراحله.", "fa-file-circle-plus", "orange"),
        "planning": ("استكمال التخطيط", "أكمل الهيكل والجدول والموارد.", "fa-pen-to-square", "purple"),
        "planned": ("مراجعة الخطة", "راجع الخطة قبل الانتقال للتنفيذ.", "fa-clipboard-check", "blue"),
        "in_progress": ("متابعة التنفيذ", "راجع أوامر التشغيل والتقدم الفعلي.", "fa-gears", "teal"),
        "completed": ("مراجعة الإغلاق", "تابع الاستلام والإغلاق الرسمي.", "fa-circle-check", "green"),
    }
    today_tasks = []
    recent_updates = []
    for item, row in zip(items, project_rows):
        action = next_actions.get(item["status"])
        if action:
            today_tasks.append({
                "title": f'{action[0]} — {item["name"]}',
                "description": action[1],
                "icon": action[2],
                "tone": action[3],
                "href": row["href"],
                "status_label": row["status_label"],
            })
        update_date = (item.get("updated_at") or item.get("directive_date")
                       or item.get("start_date") or "")
        recent_updates.append({
            "title": f'تحديث حالة المشروع: {item["name"]}',
            "project_code": item.get("project_code", ""),
            "date": str(update_date)[:10],
            "status_label": row["status_label"],
            "status": item["status"],
            "href": row["href"],
        })
    colors = {'issued': '#94a3b8', 'planning': '#ffb35c', 'planned': '#9b7cf6',
              'in_progress': '#2878ff', 'completed': '#12bd89'}
    total_projects = len(items)
    statuses = [
        {
            "code": status,
            "label": status_labels.get(status, status),
            "count": count,
            "width": round(count * 100 / total_projects) if total_projects else 0,
        }
        for status, count in status_counts.items()
    ]
    cursor = 0
    stops = []
    for row in statuses:
        end = cursor + (row['count'] * 100 / total_projects if total_projects else 0)
        row['color'] = colors.get(row['code'], '#94a3b8')
        if row['count']:
            stops.append(f"{row['color']} {cursor:.4f}% {end:.4f}%")
        cursor = end
    return {
        "budget_totals": [{'currency': currency, 'amount': f'{amount:,.2f}'}
                          for currency, amount in sorted(budgets.items())],
        "total_work_orders": sum(int(item.get('work_orders', 0)) for item in items),
        "status_gradient": ', '.join(stops) or '#e7edf6 0% 100%',
        "project_rows": project_rows,
        "total_projects": total_projects,
        "active_projects": status_counts.get("in_progress", 0),
        "planning_projects": status_counts.get("planning", 0) + status_counts.get("planned", 0),
        "issued_projects": status_counts.get("issued", 0),
        "completed_projects": status_counts.get("completed", 0),
        "open_risks": open_risks,
        "open_deviations": open_deviations,
        "status_breakdown": statuses,
        "today_tasks": today_tasks[:5],
        "recent_updates": recent_updates[:5],
    }


SECTION_PRESENTATION = {
    "baselines": ("التخطيط", "مراجعة خطط المشروع واعتماد خط الأساس.", "fa-clipboard-check"),
    "dependencies": ("التخطيط", "تنظيم العلاقات وتسلسل تنفيذ الأنشطة.", "fa-diagram-project"),
    "risks": ("الرقابة", "متابعة المخاطر وإجراءات المعالجة.", "fa-shield-halved"),
    "deviations": ("الرقابة", "رصد الانحرافات والإجراءات التصحيحية.", "fa-arrow-trend-up"),
    "cashflows": ("الرقابة", "متابعة التدفقات النقدية المسجلة للمشروع.", "fa-coins"),
    "communications": ("التخطيط", "تنظيم قنوات التواصل والجهات المعنية.", "fa-comments"),
    "reports": ("التقارير", "إعداد ومراجعة التقارير اليومية للمشروع.", "fa-file-lines"),
    "weekly-plans": ("التنفيذ", "إدارة الالتزام الأسبوعي ونتائج الإغلاق.", "fa-calendar-week"),
    "work-orders": ("التنفيذ", "متابعة أوامر التشغيل والكميات والاستهلاكات.", "fa-gears"),
}

QUICK_ACTION_SECTIONS = (
    "baselines",
    "dependencies",
    "work-orders",
    "risks",
    "deviations",
    "reports",
)


@require_GET
def _render_home(request, template, include_dashboard):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        # The backend enforces the live permission and module-enabled policy.
        module = client.get("/pm/")
        request.core_identity = client.get("/auth/me")
        request.core_modules = client.get("/modules")
        dashboard = {}
        if include_dashboard and allowed(request.core_identity, "pm.reports.view"):
            portfolio = client.get("/pm/reporting/portfolio")
            dashboard = portfolio_context(portfolio["items"])
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى إدارة المشاريع", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المشاريع غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل إدارة المشاريع؛ حاول مجددًا", status=503)
    operation_links = []
    for section, metadata in SECTIONS.items():
        if not allowed(request.core_identity, metadata[1]):
            continue
        category, description, icon = SECTION_PRESENTATION[section]
        operation_links.append({
            "section": section,
            "label": metadata[0],
            "url": "/pm/workspace/" + section + "/",
            "category": category,
            "description": description,
            "icon": icon,
        })
    operation_links_by_section = {entry["section"]: entry for entry in operation_links}
    quick_operation_links = [
        operation_links_by_section[section]
        for section in QUICK_ACTION_SECTIONS
        if section in operation_links_by_section
    ]
    secondary_operation_links = [
        entry for entry in operation_links
        if entry["section"] not in QUICK_ACTION_SECTIONS
    ]
    quick_links = []
    if allowed(request.core_identity, "pm.projects.view"):
        quick_links.append({"label": "المشاريع", "url": "/pm/projects/", "icon": "fa-folder-open"})
    if allowed(request.core_identity, "pm.projects.create"):
        quick_links.append({"label": "إضافة مشروع", "url": "/pm/projects/new/", "icon": "fa-circle-plus"})
    if allowed(request.core_identity, "pm.reports.view"):
        quick_links.append({"label": "مركز القيادة والتقارير", "url": "/pm/reporting/", "icon": "fa-chart-line"})
    if allowed(request.core_identity, "core.recycle.view"):
        quick_links.append({"label": "محذوفات إدارة المشاريع", "url": "/pm/recycle/", "icon": "fa-trash-can"})

    links_by_url = {entry["url"]: entry for entry in quick_links}
    operation_links_by_url = {entry["url"]: entry for entry in operation_links}
    primary_actions = []
    if allowed(request.core_identity, "pm.planning.view"):
        primary_actions.append({
            "label": "تخطيط مشروع",
            "url": "/pm/planning/",
            "icon": "fa-folder-open",
            "description": "وضع الأهداف والجدول الزمني وتحديد الموارد.",
            "tone": "orange",
        })
    if "/pm/projects/new/" in links_by_url:
        primary_actions.append({
            **links_by_url["/pm/projects/new/"],
            "description": "إنشاء مشروع جديد وبدء العمل عليه.",
            "tone": "green",
        })
    if allowed(request.core_identity, "pm.reports.view"):
        primary_actions.append({
            "label": "الانتقال إلى لوحة التحكم",
            "url": "/pm/dashboard/",
            "icon": "fa-chart-line",
            "description": "عرض المشاريع والمؤشرات والتقارير التفصيلية.",
            "tone": "blue",
        })
    if allowed(request.core_identity, "pm.completion.view"):
        primary_actions.append({
            "label": "مركز الاكتمال والاستلام",
            "url": "/pm/completion/",
            "icon": "fa-clipboard-check",
            "description": "مراجعة الأعمال المكتملة واستلامها وإغلاق المشروع رسمياً.",
            "tone": "teal",
        })
    if "/pm/workspace/work-orders/" in operation_links_by_url:
        primary_actions.append({
            **operation_links_by_url["/pm/workspace/work-orders/"],
            "label": "تنفيذ مشروع",
            "url": "/pm/execution/",
            "description": "مركز متابعة التنفيذ وإدارة أوامر التشغيل.",
            "tone": "purple",
        })

    primary_urls = {entry["url"] for entry in primary_actions}
    additional_links = [
        entry for entry in operation_links
        if entry["url"] not in {action["url"] for action in primary_actions}
    ]
    additional_links.extend(
        entry for entry in quick_links
        if entry["url"] not in primary_urls
        and entry["url"] not in {"/pm/dashboard/", "/pm/planning/"}
    )
    compact_links = [
        entry for entry in quick_links
        if entry["url"] in {"/pm/reporting/", "/pm/recycle/"}
    ]
    def portal_item(label, description, url, icon, permission):
        if not allowed(request.core_identity, permission):
            return None
        return {"label": label, "description": description, "url": url, "icon": icon}

    quick_access = [entry for entry in (
        portal_item("إضافة مشروع", "إنشاء مشروع جديد وبدء إدارته.", "/pm/projects/new/", "fa-circle-plus", "pm.projects.create"),
        portal_item("استعراض المشاريع", "عرض وإدارة جميع المشاريع.", "/pm/projects/", "fa-folder-open", "pm.projects.view"),
        portal_item("التخطيط", "إعداد وإدارة خطط المشاريع.", "/pm/planning/", "fa-calendar-days", "pm.planning.view"),
        portal_item("التنفيذ", "متابعة تنفيذ المشاريع والإنجاز.", "/pm/execution/", "fa-gears", "pm.execution.view"),
        portal_item("الاكتمال والاستلام والإغلاق", "مراجعة الاكتمال والاستلام والإغلاق.", "/pm/completion/", "fa-circle-check", "pm.completion.view"),
        portal_item("التقارير والرقابة", "مراقبة الأداء وتحليل المشاريع.", "/pm/reporting/", "fa-chart-line", "pm.reports.view"),
    ) if entry]

    support_items = [entry for entry in (
        portal_item("المخاطر", "إدارة مخاطر المشاريع.", "/pm/workspace/risks/", "fa-triangle-exclamation", "pm.risks.view"),
        portal_item("الوثائق والسجلات", "الوصول إلى وثائق وقرارات وسجلات المشاريع.", "/pm/projects/", "fa-file-lines", "pm.projects.view"),
        portal_item("سلة المحذوفات", "عرض واستعادة العناصر المحذوفة وفق الصلاحيات.", "/pm/recycle/", "fa-trash-can", "core.recycle.view"),
    ) if entry]

    status_counts = {
        row["code"]: row["count"] for row in dashboard.get("status_breakdown", [])
    }
    status_summary = []
    if dashboard:
        status_summary = [
            {"label": "إجمالي المشاريع", "count": dashboard["total_projects"], "icon": "fa-folder", "href": "/pm/reporting/"},
            {"label": "قيد التخطيط", "count": status_counts.get("planning", 0), "icon": "fa-calendar-days", "href": "/pm/reporting/?status=planning"},
            {"label": "قيد التنفيذ", "count": status_counts.get("in_progress", 0), "icon": "fa-play", "href": "/pm/reporting/?status=in_progress"},
            {"label": "بانتظار الإغلاق", "count": "—", "icon": "fa-clock", "href": None, "empty": "لا توجد حالة إغلاق مستقلة في عقد الحالة الحالي."},
            {"label": "المكتملة", "count": status_counts.get("completed", 0), "icon": "fa-circle-check", "href": "/pm/reporting/?status=completed"},
        ]

    portal_groups = [
        {
            "key": "quick",
            "label": "الوصول السريع",
            "description": "الوصول المباشر إلى أهم واجهات إدارة المشاريع.",
            "icon": "fa-bolt",
            "tone": "blue",
            "items": quick_access,
        },
        {
            "key": "support",
            "label": "أدوات مساندة",
            "description": "الوصول إلى الخدمات الإضافية المتعلقة بإدارة المشاريع.",
            "icon": "fa-screwdriver-wrench",
            "tone": "support",
            "items": support_items,
        },
    ]
    portal_groups = [group for group in portal_groups if group["items"]]
    primary_by_url = {entry["url"]: entry for entry in primary_actions}

    def stage_entry(entry, primary=False):
        return {
            **entry,
            "primary": primary,
            "description": entry.get("description", entry["label"]),
        }

    stage_groups = [
        {
            "key": "start",
            "label": "مرحلة البدء وإدارة المشاريع",
            "icon": "fa-bullseye",
            "items": (
                [stage_entry(primary_by_url["/pm/projects/new/"], primary=True)]
                if "/pm/projects/new/" in primary_by_url else []
            ) + [
                stage_entry(entry)
                for entry in quick_links
                if entry["url"] == "/pm/projects/"
            ],
        },
        {
            "key": "planning",
            "label": "مرحلة التخطيط",
            "icon": "fa-calendar-days",
            "items": (
                [stage_entry(primary_by_url["/pm/planning/"], primary=True)]
                if "/pm/planning/" in primary_by_url else []
            ) + [
                stage_entry(entry)
                for entry in operation_links
                if entry["category"] == "التخطيط"
            ],
        },
        {
            "key": "execution",
            "label": "مرحلة التنفيذ",
            "icon": "fa-gears",
            "items": (
                [stage_entry(primary_by_url["/pm/execution/"], primary=True)]
                if "/pm/execution/" in primary_by_url else []
            ) + [
                stage_entry(entry)
                for entry in operation_links
                if entry["category"] == "التنفيذ"
            ],
        },
        {
            "key": "completion",
            "label": "مرحلة الاكتمال والإغلاق",
            "icon": "fa-square-check",
            "items": (
                [stage_entry(primary_by_url["/pm/completion/"], primary=True)]
                if "/pm/completion/" in primary_by_url else []
            ) + [
                stage_entry(entry)
                for entry in operation_links
                if entry["category"] == "التقارير"
            ],
        },
        {
            "key": "control",
            "label": "مرحلة الرقابة والمتابعة",
            "icon": "fa-chart-column",
            "items": [
                stage_entry(entry, primary=True)
                for entry in primary_actions
                if entry["url"] == "/pm/dashboard/"
            ] + [
                stage_entry(entry)
                for entry in operation_links
                if entry["category"] == "الرقابة"
            ],
        },
    ]
    stage_groups = [group for group in stage_groups if group["items"]]
    additional_links = [
        entry for entry in additional_links
        if entry["url"] != "/pm/reporting/"
    ]
    context = {"module": module, "page_title": "إدارة المشاريع",
        "operation_links": operation_links, "quick_operation_links": quick_operation_links,
        "secondary_operation_links": secondary_operation_links, "quick_links": quick_links,
        "primary_actions": primary_actions, "additional_links": additional_links,
        "compact_links": compact_links, "stage_groups": stage_groups,
        "portal_groups": portal_groups,
        "status_summary": status_summary,
        "risk_link_available": allowed(request.core_identity, SECTIONS["risks"][1]),
        "deviation_link_available": allowed(request.core_identity, SECTIONS["deviations"][1]),
        "dashboard_available": "project_rows" in dashboard, **dashboard}
    return render(request, template, context)


def home(request):
    return _render_home(request, "pm/home.html", include_dashboard=True)


def dashboard(request):
    return _render_home(request, "pm/dashboard.html", include_dashboard=True)
