"""Baseline approval (immutable snapshots) and activity dependency graph."""
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .planning_service import PlanningService
from ..domain.planning import KINDS


class BaselineService(PlanningService):
    # ---- Baselines: immutable master-plan snapshots ----

    async def list_baselines(self, project_id):
        await self.project(project_id, 'pm.planning.view')
        rows = (await self.session.execute(text(
            'SELECT id, version, name, currency, directive_date, start_date, daily_hours, '
            'approved_by, approved_at FROM pm_plan_baselines WHERE project_id=:p '
            'ORDER BY version DESC'), {'p': project_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def approve(self, project_id):
        project = await self.project(project_id, 'pm.projects.update')
        entries = []
        for kind in ('phases', 'tasks', 'activities', 'requirements'):
            for row in [r for r in await self.repo.rows(kind, project_id) if not r['deleted_at']]:
                entries.append((kind, row))
        if not any(k == 'activities' for k, _ in entries):
            raise HTTPException(409, 'Cannot approve a plan with no activities')
        current = await self.session.scalar(text(
            'SELECT COALESCE(MAX(version),0) FROM pm_plan_baselines WHERE project_id=:p'),
            {'p': project_id})
        version = (current or 0) + 1
        baseline_id = uuid4().hex
        await self.session.execute(text(
            'INSERT INTO pm_plan_baselines '
            '(id, project_id, version, name, currency, directive_date, start_date, daily_hours, approved_by) '
            'VALUES (:id,:p,:v,:name,:cur,:dd,:sd,:dh,:by)'),
            {'id': baseline_id, 'p': project_id, 'v': version,
             'name': f"{project['project_code']} baseline {version}",
             'cur': project['currency'], 'dd': project['directive_date'],
             'sd': project['start_date'], 'dh': project['daily_hours'],
             'by': self.request.state.user_id.hex})
        for kind, row in entries:
            presented = await self.present(kind, row)
            parent = row.get(KINDS[kind][4]) if KINDS[kind][4] else None
            await self.session.execute(text(
                'INSERT INTO pm_plan_baseline_items '
                '(id, baseline_id, project_id, entity_kind, entity_id, parent_entity_id, code, name, snapshot) '
                'VALUES (:id,:b,:p,:k,:e,:parent,:code,:name,:snap)'),
                {'id': uuid4().hex, 'b': baseline_id, 'p': project_id, 'k': kind, 'e': row['id'],
                 'parent': parent, 'code': row[KINDS[kind][2]], 'name': row['name'],
                 'snap': json.dumps(presented, sort_keys=True, default=str)})
        return {'baseline_id': baseline_id, 'version': version, 'items': len(entries)}

    async def baseline(self, project_id, baseline_id):
        await self.project(project_id, 'pm.planning.view')
        header = (await self.session.execute(text(
            'SELECT id, version, name, currency, directive_date, start_date, daily_hours, '
            'approved_by, approved_at FROM pm_plan_baselines WHERE id=:b AND project_id=:p'),
            {'b': baseline_id, 'p': project_id})).mappings().first()
        if not header:
            raise HTTPException(404, 'Baseline not found')
        items = (await self.session.execute(text(
            'SELECT entity_kind, entity_id, parent_entity_id, code, name, snapshot '
            'FROM pm_plan_baseline_items WHERE baseline_id=:b ORDER BY entity_kind, code'),
            {'b': baseline_id})).mappings()
        return {'baseline': dict(header), 'items': [dict(r) for r in items]}


    # ---- Dependencies: multi predecessor/successor graph ----

    async def list_dependencies(self, project_id):
        await self.project(project_id, 'pm.planning.view')
        rows = (await self.session.execute(text(
            'SELECT id, predecessor_id, successor_id, dependency_type '
            'FROM pm_activity_dependencies WHERE project_id=:p ORDER BY created_at'),
            {'p': project_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def _would_cycle(self, project_id, predecessor, successor):
        rows = (await self.session.execute(text(
            'SELECT predecessor_id, successor_id FROM pm_activity_dependencies WHERE project_id=:p'),
            {'p': project_id})).mappings()
        adj = {}
        for r in rows:
            adj.setdefault(r['predecessor_id'], []).append(r['successor_id'])
        stack, seen = [successor], set()
        while stack:
            node = stack.pop()
            if node == predecessor:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adj.get(node, []))
        return False

    async def add_dependency(self, project_id, payload):
        project=await self.project(project_id, 'pm.planning.manage')
        if project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن تغيير اعتماديات خطة قيد التنفيذ')
        pred, succ = payload.predecessor_id.hex, payload.successor_id.hex
        if pred == succ:
            raise HTTPException(422, 'An activity cannot depend on itself')
        for aid in (pred, succ):
            act = await self.repo.get('activities', aid)
            if not act or act['project_id'] != project_id or act['deleted_at']:
                raise HTTPException(422, 'Both activities must belong to this project and be active')
        if await self._would_cycle(project_id, pred, succ):
            raise HTTPException(409, 'Dependency would create a cycle')
        dep_id = uuid4().hex
        try:
            await self.session.execute(text(
                'INSERT INTO pm_activity_dependencies '
                '(id, project_id, predecessor_id, successor_id, dependency_type, created_by) '
                'VALUES (:id,:p,:pred,:succ,:t,:by)'),
                {'id': dep_id, 'p': project_id, 'pred': pred, 'succ': succ,
                 't': payload.dependency_type, 'by': self.request.state.user_id.hex})
        except IntegrityError:
            raise HTTPException(409, 'Dependency already exists')
        await self.session.execute(text("UPDATE pm_activities SET approval_status='pending',approved_by=NULL,approved_at=NULL,approval_reason='تغيرت الاعتماديات' WHERE id=:id"),{'id':succ})
        return {'id': dep_id, 'predecessor_id': pred, 'successor_id': succ,
                'dependency_type': payload.dependency_type}

    async def remove_dependency(self, project_id, dependency_id):
        project=await self.project(project_id, 'pm.planning.manage')
        if project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن تغيير اعتماديات خطة قيد التنفيذ')
        successor=await self.session.scalar(text('SELECT successor_id FROM pm_activity_dependencies WHERE id=:id AND project_id=:p'),{'id':dependency_id,'p':project_id})
        result = await self.session.execute(text(
            'DELETE FROM pm_activity_dependencies WHERE id=:id AND project_id=:p'),
            {'id': dependency_id, 'p': project_id})
        if result.rowcount == 0:
            raise HTTPException(404, 'Dependency not found')
        await self.session.execute(text("UPDATE pm_activities SET approval_status='pending',approved_by=NULL,approved_at=NULL,approval_reason='تغيرت الاعتماديات' WHERE id=:id"),{'id':successor})
        return {'deleted': True}
