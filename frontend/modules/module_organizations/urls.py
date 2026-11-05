from django.urls import path
from .views import list, ajax_orgs, ajax_entity_types

app_name = "organizations"

urlpatterns = [
    # Page
    path("", list.organizations_list, name="list"),
    
    # Entities API
    path("ajax/list/", ajax_orgs.ajax_orgs_list, name="ajax_list"),
    path("ajax/entity-types/", ajax_orgs.ajax_entity_types, name="ajax_types"),
    path("ajax/create/", ajax_orgs.ajax_org_create, name="ajax_create"),
    path("ajax/update/<uuid:org_id>/", ajax_orgs.ajax_org_update, name="ajax_update"),
    path("ajax/delete/<uuid:org_id>/", ajax_orgs.ajax_org_delete, name="ajax_delete"),
    
    # Entity Types API
    path("ajax/entity-types/create/", ajax_entity_types.ajax_entity_type_create, name="ajax_type_create"),
    path("ajax/entity-types/<uuid:type_id>/update/", ajax_entity_types.ajax_entity_type_update, name="ajax_type_update"),
    path("ajax/entity-types/<uuid:type_id>/delete/", ajax_entity_types.ajax_entity_type_delete, name="ajax_type_delete"),
]
