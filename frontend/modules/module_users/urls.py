from django.urls import path
from .views import list, detail, create, edit, delete, profile, ajax_list, ajax_status, ajax_create, ajax_update, ajax_delete, ajax_permissions, roles, ajax_roles

app_name = "users"

urlpatterns = [
    path("", list.users_list, name="list"),
    path("roles/", roles.roles_management, name="roles"),
    path("<uuid:user_id>/", detail.users_detail, name="detail"),
    path("create/", create.users_create, name="create"),
    path("<uuid:user_id>/edit/", edit.users_edit, name="edit"),
    path("<uuid:user_id>/delete/", delete.users_delete, name="delete"),
    path("profile/", profile.users_profile, name="profile"),
    path("ajax/list/", ajax_list.ajax_users_list, name="ajax_list"),
    path("ajax/permissions/", ajax_permissions.ajax_permissions_list, name="ajax_permissions"),
    path("ajax/create/", ajax_create.ajax_users_create, name="ajax_create"),
    path("ajax/update/<uuid:user_id>/", ajax_update.ajax_users_update, name="ajax_update"),
    path("ajax/delete/<uuid:user_id>/", ajax_delete.ajax_users_delete, name="ajax_delete"),
    path("ajax/<uuid:user_id>/status/", ajax_status.ajax_update_status, name="ajax_status"),
    path("ajax/role/create/", ajax_roles.ajax_role_create, name="ajax_role_create"),
    path("ajax/role/<int:role_id>/update/", ajax_roles.ajax_role_update, name="ajax_role_update"),
    path("ajax/role/<int:role_id>/delete/", ajax_roles.ajax_role_delete, name="ajax_role_delete"),
    path("ajax/role/<int:role_id>/permissions/", ajax_roles.ajax_role_permissions, name="ajax_role_permissions"),
    path("ajax/role/<int:role_id>/link-permission/", ajax_roles.ajax_link_permission, name="ajax_link_permission"),
    path("ajax/role/<int:role_id>/unlink-permission/", ajax_roles.ajax_unlink_permission, name="ajax_unlink_permission"),
    path("ajax/permission/create/", ajax_roles.ajax_permission_create, name="ajax_perm_create"),
    path("ajax/permission/<int:perm_id>/update/", ajax_roles.ajax_permission_update, name="ajax_perm_update"),
    path("ajax/permission/<int:perm_id>/delete/", ajax_roles.ajax_permission_delete, name="ajax_perm_delete"),
    path("ajax/roles-list/", ajax_list.ajax_roles_list, name="ajax_roles_list"),
    path("ajax/organizations/", ajax_list.ajax_organizations_list, name="ajax_orgs"),
    ]


