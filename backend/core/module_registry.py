"""Explicit module definitions. Business packages register only at composition."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuleManifest:
    code: str
    name: str
    href: str
    permission: str = ""
    version: str = "1.0"
    enabled: bool = True
    dependencies: tuple = ()
    permissions: tuple = ()
    settings: dict = field(default_factory=dict)
    notification_templates: dict = field(default_factory=dict)
    unit_scoped_permissions: tuple = ()
    entity_types: tuple = ()
    api_prefixes: tuple = ()
    routers: tuple = ()
    schema_version: str = "0002_core_access"


class ModuleRegistry:
    def __init__(self):
        self.modules = {}
        self.entity_resolvers = {}
        self.recycle_handlers = {}
        self.source_reference_handlers = {}

    def register_source_reference(self, module_code, source_type, validator):
        """Register an owner callback for cross-module source document references."""
        if module_code not in self.modules or not source_type or not callable(validator):
            raise ValueError("Registered source owner and validator are required")
        key = (module_code, source_type)
        if key in self.source_reference_handlers:
            raise ValueError("Source reference handler must be unique")
        self.source_reference_handlers[key] = validator

    async def validate_source_reference(
        self, module_code, source_type, session, organization_id, source_id,
        document_type, warehouse_id, lines, require_posted=False,
    ):
        from fastapi import HTTPException
        validator = self.source_reference_handlers.get((module_code, source_type))
        if validator is None:
            raise HTTPException(409, "SOURCE_REFERENCE_WORKFLOW_UNAVAILABLE")
        return await validator(
            session, organization_id, source_id, document_type, warehouse_id,
            lines, require_posted,
        )

    def register_recycle(self, module_code, entity_type, permissions, authorize, restore, purge):
        """Owner callbacks run in Core's transaction; never commit in a callback.

        authorize(session, actor, admin, scopes, entity_id) checks authoritative
        owner/organization data, not recycle metadata. Mutations enforce lifecycle.
        """
        module = self.modules[module_code]
        if entity_type not in module.entity_types or not entity_type.startswith(module_code + '.'):
            raise ValueError('Recycle entity must be declared by its owner')
        if entity_type in self.recycle_handlers or set(permissions) != {'view', 'restore', 'purge'}:
            raise ValueError('Unique handler and action permissions required')
        if any(p not in module.permissions for p in permissions.values()):
            raise ValueError('Recycle permissions must be declared by the owner')
        if not all(callable(fn) for fn in (authorize, restore, purge)):
            raise ValueError('Recycle callbacks required')
        self.recycle_handlers[entity_type] = (module_code, permissions, authorize, restore, purge)

    def register_entity(self, module_code, entity_type, permission, resolver):
        module = self.modules[module_code]
        if entity_type not in module.entity_types or not entity_type.startswith(module_code + "."):
            raise ValueError("Entity type must be declared in its module namespace")
        if entity_type in self.entity_resolvers or not permission or not callable(resolver):
            raise ValueError("Unique entity type, permission and resolver are required")
        self.entity_resolvers[entity_type] = (module_code, permission, resolver)

    async def resolve_entity(self, entity_type, entity_id, request, session):
        from fastapi import HTTPException
        from core.access import require
        entry = self.entity_resolvers.get(entity_type)
        from modules.module_settings.application.module_policy import enabled_modules
        enabled = await enabled_modules(session)
        if entry and not enabled.get(entry[0]):
            raise HTTPException(404, "Entity module disabled")
        if entry is None or not self.modules.get(entry[0]) or not self.modules[entry[0]].enabled:
            raise HTTPException(404, "Entity type unavailable")
        _, permission, resolver = entry
        require(request, permission)
        scopes = request.state.permission_scopes.get(permission, {"self"})
        result = await resolver(session, request.state.user, request.state.is_admin, scopes, entity_id)
        if result is None:
            raise HTTPException(404, "Entity unavailable within assigned scope")
        href = result.get("href", "")
        if not href.startswith("/") or href.startswith("//") or "\\" in href:
            raise ValueError("Entity resolver must return a local application route")
        return {"type": entity_type, "id": str(entity_id), "label": result["label"], "href": href}

    def register(self, manifest):
        if manifest.code in self.modules or any(m.href == manifest.href for m in self.modules.values()):
            raise ValueError("Duplicate module code or navigation route")
        for prefix in manifest.api_prefixes:
            if any(prefix == existing or prefix.startswith(existing + "/") or existing.startswith(prefix + "/")
                   for m in self.modules.values() for existing in m.api_prefixes):
                raise ValueError("Duplicate module API prefix")
        if manifest.schema_version != "0002_core_access":
            raise ValueError("Unsupported schema version")
        if not set(manifest.unit_scoped_permissions).issubset(manifest.permissions):
            raise ValueError("Unit-scoped permissions must be declared by their module")
        for router in manifest.routers:
            for route in router.routes:
                if not any(route.path == p or route.path.startswith(p + "/") for p in manifest.api_prefixes):
                    raise ValueError("Module route must be inside its declared API prefixes")
        self.modules[manifest.code] = manifest

    def unit_scope_owner(self, permission):
        for module in self.modules.values():
            if permission in module.unit_scoped_permissions:
                return module.code
        return None

    def validate(self):
        for module in self.modules.values():
            if module.enabled and any(d not in self.modules or not self.modules[d].enabled for d in module.dependencies):
                raise ValueError("Missing enabled module dependency: " + module.code)
        def visit(code, stack):
            if code in stack:
                raise ValueError("Circular module dependency")
            for dependency in self.modules[code].dependencies:
                if dependency in self.modules:
                    visit(dependency, stack | {code})
        for code in self.modules:
            visit(code, set())

    def mount(self, app):
        self.validate()
        for module in self.modules.values():
            if module.enabled:
                for router in module.routers:
                    app.include_router(router)

    async def install_definitions(self, session):
        """Register additive definitions without overwriting existing user values."""
        import json
        from uuid import uuid4
        from sqlalchemy import text
        self.validate()
        for module in self.modules.values():
            if not module.enabled:
                continue
            for code in module.permissions:
                if not code.startswith(module.code + "."):
                    raise ValueError("Module permission must use its namespace")
                await session.execute(text("INSERT OR IGNORE INTO permissions(code,name,system,resource,action) VALUES(:code,:code,:system,:resource,:action)"),
                    dict(code=code, system=module.code, resource=code.split(".")[1], action=code.split(".")[-1]))
            for key, definition in module.settings.items():
                if not key.startswith(module.code + "."):
                    raise ValueError("Module setting must use its namespace")
                await session.execute(text("INSERT OR IGNORE INTO system_settings(id,key,value,default_value,data_type,is_active,is_encrypted,is_required) VALUES(:id,:key,:value,:value,:kind,1,0,1)"),
                    dict(id=uuid4().hex, key=key, value=json.dumps(definition["default"]), kind=definition["type"]))
            for code, definition in module.notification_templates.items():
                if not code.startswith(module.code + "."):
                    raise ValueError("Template must use module namespace")
                await session.execute(text("INSERT OR IGNORE INTO notification_templates(id,type,subject_template,body_template,channel,is_active) VALUES(:id,:code,:subject,:body,'in_app',1)"),
                    dict(id=uuid4().hex, code=code, subject=definition["title"], body=definition["body"]))

    def visible(self, permissions, admin=False):
        return [m for m in self.modules.values() if m.enabled and (admin or not m.permission or m.permission in permissions)]


registry = ModuleRegistry()
for manifest in (
    ModuleManifest("users", "المستخدمون والصلاحيات", "/users/", "core.users.view", api_prefixes=("/api/v1/users", "/api/v1/roles", "/api/v1/permissions")),
    ModuleManifest("organizations", "الهيكل التنظيمي", "/organizations/tree/", "core.organizations.view", api_prefixes=("/api/v1/org-units",)),
    ModuleManifest("entities", "دليل الجهات والكيانات", "/organizations/", "core.organizations.view", api_prefixes=("/api/v1/entities", "/api/v1/organizations")),
    ModuleManifest("settings", "الإعدادات", "/settings/", "core.settings.view", api_prefixes=("/api/v1/settings",)),
    ModuleManifest("notifications", "الإشعارات", "/notifications/", api_prefixes=("/api/v1/notifications",)),
    ModuleManifest("audit", "سجل التدقيق", "/audit/", "core.audit.view", api_prefixes=("/api/v1/audit",)),
    ModuleManifest("currency", "العملات وأسعار الصرف", "/currency/", "core.currency.view", api_prefixes=("/api/v1/currency",)),
    ModuleManifest("recycle", "سلة المحذوفات", "/recycle/", "core.recycle.view", api_prefixes=("/api/v1/recycle",)),
):
    registry.register(manifest)
registry.validate()
