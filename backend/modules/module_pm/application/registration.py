"""Owner callbacks installed only by the application's composition root."""
from uuid import UUID
from ..domain.planning import KINDS, in_scope
from .planning_service import PlanningService, permission


def register_entities(registry):
    for kind in KINDS:
        register_kind(registry, kind)


def register_kind(registry, kind):
    async def owner(session, actor, admin, scopes, entity_id):
        repo = PlanningService(session).repo
        row = await repo.get(kind, UUID(str(entity_id)).hex)
        if row is None:
            return None, None
        project = row if kind == 'projects' else await repo.get('projects', row['project_id'])
        return (row, project) if project and in_scope(project, actor, admin, scopes) else (None, None)

    async def authorize(session, actor, admin, scopes, entity_id):
        row, _ = await owner(session, actor, admin, scopes, entity_id)
        return bool(row and row['deleted_at'])

    async def resolve(session, actor, admin, scopes, entity_id):
        row, project = await owner(session, actor, admin, scopes, entity_id)
        if not row or row['deleted_at'] or project['deleted_at']:
            return None
        return {'label': row['name'], 'href': f'/pm/projects/{UUID(project["id"])}/'}

    async def restore(session, entity_id, actor_id):
        await PlanningService(session).recover(kind, UUID(str(entity_id)).hex, actor_id)

    async def purge(session, entity_id, actor_id):
        await PlanningService(session).recover(kind, UUID(str(entity_id)).hex, actor_id, purge=True)

    registry.register_entity('pm', 'pm.' + kind, permission(kind, 'view'), resolve)
    registry.register_recycle('pm', 'pm.' + kind,
        {'view': permission(kind, 'view'), 'restore': permission(kind, 'update'), 'purge': 'pm.projects.purge'},
        authorize, restore, purge)
