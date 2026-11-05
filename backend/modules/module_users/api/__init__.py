# modules/module_users/api/__init__.py
from .users_controller import auth_router, users_router
from .roles_controller import roles_router
from .permissions_controller import permissions_router

__all__ = [
    "auth_router",
    "users_router",
    "roles_router",
    "permissions_router",
]
