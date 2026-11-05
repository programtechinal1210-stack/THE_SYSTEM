from django.urls import path
from .views import home, dashboard
from .views.project_create import create_project, next_project_code
from .views.planning import planning
from .views.recycle import recycle
from .views.reporting import reporting, portfolio, report_center
from .views.operations import operations, workspace
from .views.execution_center import execution_center
from .views.completion import (
    completion_center, completion_document_download, completion_receipt, completion_workspace,
    completion_report,
)
from .views.approval import approval
from .views.hierarchy import hierarchy
from .views.copy import copy_plan
from .views.attachments import attachments
from .services.operations import SECTIONS, CONTROL

app_name = "pm"
urlpatterns = [path("", home, name="home"),
    path('execution/', execution_center, name='execution-center'),
    path('completion/', completion_center, name='completion-center'),
    path('completion/projects/<uuid:project_id>/', completion_workspace, name='completion-workspace'),
    path('completion/projects/<uuid:project_id>/report/', completion_report, name='completion-report'),
    path('completion/projects/<uuid:project_id>/receipts/<uuid:case_id>/', completion_receipt, name='completion-receipt'),
    path('completion/projects/<uuid:project_id>/cases/<uuid:case_id>/documents/<uuid:attachment_id>/', completion_document_download, name='completion-document-download'),
    path("dashboard/", dashboard, name="dashboard"),
    path('planning/', planning, name='planning-dashboard'),
    path('projects/<uuid:project_id>/copy/',copy_plan,name='copy-plan'),
    path('projects/<uuid:project_id>/activities/<uuid:activity_id>/attachments/',attachments,name='attachment-upload'),
    path('projects/<uuid:project_id>/activities/<uuid:activity_id>/attachments/<uuid:attachment_id>/',attachments,name='attachment-download'),
    path('projects/<uuid:project_id>/approval/',approval,name='approval'),
    path('projects/<uuid:project_id>/hierarchy/',hierarchy,name='hierarchy'),
    path('projects/<uuid:entity_id>/document/',planning,{'action':'document'},name='plan-document'),
    path('projects/<uuid:entity_id>/slides/',planning,{'action':'slides'},name='plan-slides'),
    path('workspace/<str:section>/',workspace,name='workspace'),
    path('reporting/',report_center,name='portfolio'),
    path('reporting/portfolio/',portfolio,name='portfolio-report'),
    path('recycle/', recycle, name='recycle'),
    path('projects/', planning, name='projects'),
    path('projects/next-code/', next_project_code, name='project-next-code'),
    path('projects/new/', create_project, name='project-create'),
    path('projects/edit/', planning, {'action':'edit'}, name='project-create-legacy'),
    path('projects/<uuid:entity_id>/', planning, name='project-detail'),
    path('projects/<uuid:entity_id>/edit/', planning, {'action':'edit'}, name='project-edit'),
    path('projects/<uuid:entity_id>/delete/', planning, {'action':'delete'}, name='project-delete'),
    path('projects/<uuid:project_id>/reporting/', reporting, name='reporting'),
    *[path('projects/<uuid:project_id>/' + section + '/', operations, {'section':section}, name=section) for section in SECTIONS],
    *[path('projects/<uuid:project_id>/' + section + '/<uuid:entity_id>/', operations, {'section':section}, name=section+'-detail') for section in SECTIONS if section!='dependencies'],
    *[path('projects/<uuid:project_id>/' + section + '/<uuid:entity_id>/' + action + '/', operations, {'section':section,'action':action}, name=section+'-'+action) for section in CONTROL for action in ('edit','delete')],
    path('projects/<uuid:project_id>/<str:kind>/', planning, name='planning-list'),
    path('projects/<uuid:project_id>/<str:kind>/edit/', planning, {'action':'edit'}, name='planning-create'),
    path('projects/<uuid:project_id>/<str:kind>/<uuid:entity_id>/', planning, name='planning-detail'),
    path('projects/<uuid:project_id>/<str:kind>/<uuid:entity_id>/edit/', planning, {'action':'edit'}, name='planning-edit'),
    path('projects/<uuid:project_id>/<str:kind>/<uuid:entity_id>/delete/', planning, {'action':'delete'}, name='planning-delete'),
]
