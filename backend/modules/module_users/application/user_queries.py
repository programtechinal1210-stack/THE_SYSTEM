from sqlalchemy import select
from modules.module_users.infrastructure.models.user_model import UserModel


def scoped_users(request, search="", organization_id=None, is_active=None):
    query = select(UserModel)
    if search:
        query = query.where(UserModel.full_name.contains(search) | UserModel.username.contains(search))
    if organization_id:
        query = query.where(UserModel.organization_id == organization_id)
    if is_active is not None:
        query = query.where(UserModel.is_active.is_(is_active))
    if not request.state.is_admin and "institution" not in request.state.scopes:
        if "organization" in request.state.scopes:
            query = query.where(UserModel.organization_id == request.state.user.organization_id)
        else:
            query = query.where(UserModel.id == request.state.user.id)
    return query
