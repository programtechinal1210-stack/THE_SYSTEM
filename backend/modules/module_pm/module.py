"""PM manifest consumed by the existing application composition root."""
from core.module_registry import ModuleManifest
from . import VERSION
from .api import router
from .api.planning_controller import router as planning_router
from .api.baseline_controller import router as baseline_router
from .api.control_controller import router as control_router
from .api.execution_controller import router as execution_router
from .api.wep_controller import router as wep_router
from .api.report_controller import router as report_router
from .api.ui_controller import router as ui_router
from .api.planning_workflow_controller import router as planning_workflow_router
from .api.planning_hierarchy_controller import router as planning_hierarchy_router
from .api.planning_copy_controller import router as planning_copy_router
from .api.attachment_controller import router as attachment_router
from .api.completion_controller import router as completion_router
from .api.schedule_version_controller import router as schedule_version_router
from .api.actual_read_controller import router as actual_read_router

manifest = ModuleManifest(
    code="pm", name="إدارة المشاريع", href="/pm/", permission="pm.access",
    version=VERSION, enabled=True, api_prefixes=("/api/v1/pm",), routers=(router, planning_router, baseline_router, control_router, execution_router, wep_router, report_router, ui_router, planning_workflow_router, planning_hierarchy_router, planning_copy_router, attachment_router, completion_router, schedule_version_router, actual_read_router),
    entity_types=('pm.projects', 'pm.phases', 'pm.tasks', 'pm.activities', 'pm.requirements'),
    notification_templates={'pm.project_assigned': {'title': 'إسناد إدارة مشروع', 'body': 'تم إسناد إدارة المشروع {project} إليك'}},
    permissions=("pm.access",
                 "pm.projects.view", "pm.projects.create", "pm.projects.update", "pm.projects.delete", "pm.projects.purge",
                 "pm.planning.view", "pm.planning.manage",
                 "pm.risks.view", "pm.risks.manage",
                 "pm.execution.view", "pm.execution.manage",
                 "pm.schedule.view", "pm.schedule.manage", "pm.schedule.propose",
                 "pm.schedule.approve", "pm.schedule.emergency_authorize",
                 "pm.wep.view", "pm.wep.manage",
                 "pm.completion.view", "pm.completion.review", "pm.completion.issues.manage",
                 "pm.completion.issues.verify", "pm.completion.accept", "pm.completion.close",
                 "pm.completion.documents.view", "pm.completion.documents.manage",
                 "pm.reports.view",
                 "pm.portability.manage"),
)
