"""Organization-scoped category and asset registry operations."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import allowed, require

METER_UNITS = {"hours": "h", "distance": "km", "cycles": "cycle", "energy": "kWh", "none": "none"}
ASSET_COLUMNS = (
    "id", "organization_id", "asset_code", "asset_name", "category_id", "serial_number",
    "manufacturer", "model", "ownership_type", "owner_entity_id", "responsible_entity_id",
    "custodian_ref_type", "custodian_ref_id", "home_location", "current_location",
    "lifecycle_status", "technical_status", "meter_initial", "meter_latest", "meter_last_at",
    "meter_type_locked", "meter_unit_locked", "meter_generation", "meter_normalized_latest",
    "readiness_projection_version", "acquisition_date", "acquisition_value", "currency_id",
    "rental_contract_ref", "specifications", "notes", "created_at", "updated_at", "created_by",
    "updated_by", "version",
)
CATEGORY_COLUMNS = (
    "id", "organization_id", "category_code", "name_ar", "name_en", "parent_id", "meter_type",
    "meter_unit", "output_unit", "fuel_unit", "spec_schema", "inspection_schema",
    "maintenance_rules", "is_active", "created_at", "updated_at", "created_by", "updated_by",
    "version",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hex(value):
    return UUID(str(value)).hex if value else None


def _parse_json(row, fields):
    result = dict(row)
    for field in fields:
        result[field] = json.loads(result[field])
    return result


class EquipmentRegistryService:
    def __init__(self, session, request):
        self.session = session
        self.request = request

    async def asset_form_options(self, organization_id=None):
        require(self.request, "equipment.assets.manage")
        require(self.request, "equipment.categories.view")
        organization_id = await self._organization(
            organization_id, "equipment.assets.manage", create=True
        )
        category_organization_id = await self._organization(
            organization_id, "equipment.categories.view"
        )
        if category_organization_id != organization_id:
            raise HTTPException(404, "Equipment category scope unavailable")
        categories = (
            await self.session.execute(
                text(
                    "SELECT id, category_code, name_ar, name_en, meter_type, meter_unit, "
                    "output_unit FROM eq_categories "
                    "WHERE organization_id=:org AND is_active=1 AND deleted_at IS NULL "
                    "ORDER BY name_ar, category_code"
                ),
                {"org": organization_id},
            )
        ).mappings().all()
        organization_units = (
            await self.session.execute(
                text(
                    "WITH RECURSIVE allowed_units(id, name, parent_id) AS ("
                    " SELECT id, name, parent_id FROM organizations "
                    " WHERE id=:org AND is_active=1"
                    " UNION"
                    " SELECT child.id, child.name, child.parent_id FROM organizations child"
                    " JOIN allowed_units parent ON child.parent_id=parent.id"
                    " WHERE child.is_active=1"
                    ") SELECT id, name, parent_id FROM allowed_units ORDER BY name"
                ),
                {"org": organization_id},
            )
        ).mappings().all()
        currencies = (
            await self.session.execute(
                text(
                    "SELECT id, code, name, symbol FROM core_currencies "
                    "WHERE is_active=1 ORDER BY code"
                )
            )
        ).mappings().all()
        return {
            "organization_id": organization_id,
            "categories": [dict(row) for row in categories],
            "organization_units": [dict(row) for row in organization_units],
            "currencies": [dict(row) for row in currencies],
        }

    def _actor(self):
        return self.request.state.user

    def _admin(self):
        return bool(self.request.state.is_admin)

    def _scopes(self, permission):
        return self.request.state.permission_scopes.get(permission, {"self"})

    def _has_organization_permission(self, permission):
        scopes = self._scopes(permission)
        return allowed(self.request, permission) and (
            self._admin() or "institution" in scopes or "organization" in scopes
        )

    async def _organization(self, requested, permission, create=False):
        actor_org = _hex(getattr(self._actor(), "organization_id", None))
        scopes = self._scopes(permission)
        broad = self._admin() or "institution" in scopes
        if not broad:
            if "organization" not in scopes or not actor_org:
                raise HTTPException(403, "Organization scope is required")
            if requested and _hex(requested) != actor_org:
                raise HTTPException(404, "Equipment scope unavailable")
            organization_id = actor_org
        else:
            organization_id = _hex(requested) or actor_org
            if not organization_id:
                raise HTTPException(422, "organization_id is required")
        active = await self.session.scalar(
            text("SELECT 1 FROM organizations WHERE id=:org AND is_active=1"),
            {"org": organization_id},
        )
        if not active:
            raise HTTPException(422, "Unknown or inactive organization")
        return organization_id

    async def _entity_in_organization(self, entity_id, organization_id, field):
        if entity_id is None:
            return None
        found = await self.session.scalar(
            text(
                "WITH RECURSIVE allowed_units(id) AS ("
                " SELECT id FROM organizations WHERE id=:org AND is_active=1"
                " UNION SELECT child.id FROM organizations child"
                " JOIN allowed_units parent ON child.parent_id=parent.id WHERE child.is_active=1"
                ") SELECT 1 FROM allowed_units WHERE id=:entity"
            ),
            {"org": organization_id, "entity": _hex(entity_id)},
        )
        if not found:
            raise HTTPException(422, f"{field} must be an active unit within the equipment organization")
        return _hex(entity_id)

    async def _visible_org(self, organization_id, permission):
        scopes = self._scopes(permission)
        actor_org = _hex(getattr(self._actor(), "organization_id", None))
        if self._admin() or "institution" in scopes or (
            "organization" in scopes and organization_id == actor_org
        ):
            return
        raise HTTPException(404, "Equipment record unavailable within scope")

    async def list_categories(self, organization_id=None, search=None, skip=0, limit=100):
        permission = "equipment.categories.view"
        require(self.request, permission)
        org = await self._organization(organization_id, permission)
        query = (
            "SELECT " + ",".join(CATEGORY_COLUMNS) +
            " FROM eq_categories WHERE organization_id=:org AND deleted_at IS NULL"
        )
        params = {"org": org, "skip": skip, "limit": limit}
        if search:
            query += " AND (category_code LIKE :search OR name_ar LIKE :search OR name_en LIKE :search)"
            params["search"] = f"%{search.strip()}%"
        query += " ORDER BY category_code LIMIT :limit OFFSET :skip"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [_parse_json(row, ("spec_schema", "inspection_schema", "maintenance_rules")) for row in rows]}

    async def create_category(self, payload, organization_id=None):
        permission = "equipment.categories.manage"
        require(self.request, permission)
        values = payload.model_dump(mode="json")
        org = await self._organization(organization_id, permission, create=True)
        expected = METER_UNITS[values["meter_type"]]
        if values["meter_unit"] != expected:
            raise HTTPException(422, f"meter_unit must be {expected} for {values['meter_type']}")
        parent = await self._entity_category(values.get("parent_id"), org, "parent_id")
        now, identifier, actor = _now(), uuid4().hex, self.request.state.user_id.hex
        record = {
            "id": identifier, "organization_id": org, **values, "parent_id": parent,
            "spec_schema": json.dumps(values["spec_schema"], ensure_ascii=False, separators=(",", ":")),
            "inspection_schema": json.dumps(values["inspection_schema"], ensure_ascii=False, separators=(",", ":")),
            "maintenance_rules": json.dumps(values["maintenance_rules"], ensure_ascii=False, separators=(",", ":")),
            "created_at": now, "updated_at": now, "created_by": actor, "updated_by": actor, "version": 1,
        }
        try:
            await self._insert("eq_categories", CATEGORY_COLUMNS, record)
        except IntegrityError:
            raise HTTPException(409, "Category code already exists in this organization") from None
        self._audit("equipment.category", identifier, new={"category_code": record["category_code"]})
        return await self._category(identifier, org)

    async def update_category(self, identifier, payload):
        permission = "equipment.categories.manage"
        require(self.request, permission)
        current = (await self.session.execute(
            text(
                "SELECT " + ",".join(CATEGORY_COLUMNS) +
                " FROM eq_categories WHERE id=:id AND deleted_at IS NULL"
            ),
            {"id": _hex(identifier)},
        )).mappings().first()
        if not current:
            raise HTTPException(404, "Equipment category unavailable")
        await self._visible_org(current["organization_id"], permission)
        values = payload.model_dump(mode="json", exclude_unset=True)
        expected_version = values.pop("version")
        if not values:
            raise HTTPException(422, "At least one editable field is required")

        next_meter_type = values.get("meter_type", current["meter_type"])
        next_meter_unit = values.get("meter_unit", current["meter_unit"])
        if next_meter_unit != METER_UNITS[next_meter_type]:
            raise HTTPException(422, f"meter_unit must be {METER_UNITS[next_meter_type]} for {next_meter_type}")
        if next_meter_type != current["meter_type"] or next_meter_unit != current["meter_unit"]:
            has_assets = await self.session.scalar(
                text("SELECT 1 FROM eq_assets WHERE organization_id=:org AND category_id=:id AND deleted_at IS NULL LIMIT 1"),
                {"org": current["organization_id"], "id": current["id"]},
            )
            if has_assets:
                raise HTTPException(409, "Category meter type is locked while assets reference it")
        if "parent_id" in values:
            parent_id = await self._entity_category(
                values["parent_id"], current["organization_id"], "parent_id"
            )
            if parent_id:
                is_descendant = await self.session.scalar(
                    text(
                        "WITH RECURSIVE descendants(id) AS ("
                        " SELECT id FROM eq_categories WHERE id=:id AND organization_id=:org"
                        " UNION SELECT child.id FROM eq_categories child"
                        " JOIN descendants parent ON child.parent_id=parent.id"
                        " WHERE child.organization_id=:org AND child.deleted_at IS NULL"
                        ") SELECT 1 FROM descendants WHERE id=:parent"
                    ),
                    {"id": current["id"], "org": current["organization_id"], "parent": parent_id},
                )
                if is_descendant:
                    raise HTTPException(422, "Category hierarchy cannot contain a cycle")
            values["parent_id"] = parent_id
        for field in ("spec_schema", "inspection_schema", "maintenance_rules"):
            if field in values:
                values[field] = json.dumps(values[field], ensure_ascii=False, separators=(",", ":"))
        values.update(
            updated_at=_now(),
            updated_by=self.request.state.user_id.hex,
            version=expected_version + 1,
        )
        assignments = ",".join(f"{column}=:{column}" for column in values)
        values.update(
            id=current["id"],
            organization_id=current["organization_id"],
            expected_version=expected_version,
        )
        try:
            result = await self.session.execute(
                text(
                    f"UPDATE eq_categories SET {assignments} "
                    "WHERE id=:id AND organization_id=:organization_id "
                    "AND version=:expected_version AND deleted_at IS NULL"
                ),
                values,
            )
        except IntegrityError:
            raise HTTPException(409, "Category code already exists in this organization") from None
        if result.rowcount != 1:
            raise HTTPException(409, "Equipment category changed; reload before editing")
        self._audit(
            "equipment.category",
            current["id"],
            old={"version": expected_version},
            new={"version": expected_version + 1},
        )
        return await self._category(current["id"], current["organization_id"])

    async def _entity_category(self, category_id, organization_id, field, active=False):
        if category_id is None:
            return None
        row = (await self.session.execute(
            text("SELECT id,is_active FROM eq_categories WHERE id=:id AND organization_id=:org AND deleted_at IS NULL"),
            {"id": _hex(category_id), "org": organization_id},
        )).mappings().first()
        if not row or (active and not row["is_active"]):
            raise HTTPException(422, f"{field} must reference an available category in this organization")
        return row["id"]

    async def _category(self, identifier, organization_id):
        row = (await self.session.execute(
            text("SELECT " + ",".join(CATEGORY_COLUMNS) + " FROM eq_categories WHERE id=:id AND organization_id=:org"),
            {"id": identifier, "org": organization_id},
        )).mappings().one()
        return _parse_json(row, ("spec_schema", "inspection_schema", "maintenance_rules"))

    async def list_assets(
        self,
        organization_id=None,
        search=None,
        skip=0,
        limit=100,
        category_id=None,
        lifecycle_status=None,
        technical_status=None,
        responsible_entity_id=None,
        location=None,
        sort_by="asset_code",
        sort_dir="asc",
    ):
        permission = "equipment.assets.view"
        require(self.request, permission)
        org = await self._organization(organization_id, permission)
        conditions = ["a.organization_id=:org", "a.deleted_at IS NULL"]
        params = {"org": org, "skip": skip, "limit": limit, "now": _now()}
        if search:
            conditions.append(
                "(a.asset_code LIKE :search OR a.asset_name LIKE :search OR a.serial_number LIKE :search)"
            )
            params["search"] = f"%{search.strip()}%"
        for column, value in (
            ("category_id", _hex(category_id)),
            ("lifecycle_status", lifecycle_status),
            ("technical_status", technical_status),
            ("responsible_entity_id", _hex(responsible_entity_id)),
            ("current_location", location),
        ):
            if value is not None and value != "":
                conditions.append(f"a.{column}=:{column}")
                params[column] = value
        where = " AND ".join(conditions)
        count = await self.session.scalar(
            text(
                "SELECT COUNT(*) FROM eq_assets a "
                "JOIN eq_categories c ON c.organization_id=a.organization_id AND c.id=a.category_id "
                f"WHERE {where}"
            ),
            params,
        )

        assignment_projection = ""
        can_view_assignments = self._has_organization_permission("equipment.assignments.view")
        if can_view_assignments:
            assignment_projection = (
                ",(SELECT x.status FROM eq_assignments x "
                "WHERE x.organization_id=a.organization_id AND x.asset_id=a.id "
                "AND x.status IN ('approved','dispatched','active','suspended') "
                "AND x.planned_start_at<=:now AND x.planned_end_at>:now "
                "ORDER BY CASE x.status WHEN 'active' THEN 0 WHEN 'suspended' THEN 1 "
                "WHEN 'dispatched' THEN 2 ELSE 3 END,x.planned_start_at DESC LIMIT 1) "
                "AS assignment_status"
            )
        inspection_projection = ""
        can_view_inspection_blocks = self._has_organization_permission(
            "equipment.inspections.view"
        )
        if can_view_inspection_blocks:
            inspection_projection = (
                ",(SELECT group_concat(i.block_reason_code, ',') FROM eq_inspections i "
                "WHERE i.organization_id=a.organization_id AND i.asset_id=a.id "
                "AND i.block_status='active') AS inspection_blocker_reasons"
            )
        maintenance_projection = ""
        can_view_maintenance_blocks = self._has_organization_permission(
            "equipment.maintenance.view"
        )
        if can_view_maintenance_blocks:
            maintenance_projection = (
                ",(SELECT group_concat(m.block_reason_code, ',') FROM eq_maintenance_orders m "
                "WHERE m.organization_id=a.organization_id AND m.asset_id=a.id "
                "AND m.block_status='active') AS maintenance_blocker_reasons"
            )

        sort_columns = {
            "asset_code": "a.asset_code",
            "asset_name": "a.asset_name",
            "category_name": "c.name_ar",
            "lifecycle_status": "a.lifecycle_status",
            "current_location": "a.current_location",
            "created_at": "a.created_at",
        }
        sort_column = sort_columns[sort_by]
        sort_direction = "DESC" if sort_dir == "desc" else "ASC"
        rows = (await self.session.execute(
            text(
                "SELECT a." + ",a.".join(ASSET_COLUMNS)
                + ",c.category_code,c.name_ar AS category_name,"
                + "owner.name AS owner_entity_name,responsible.name AS responsible_entity_name"
                + assignment_projection + inspection_projection + maintenance_projection
                + " FROM eq_assets a "
                + "JOIN eq_categories c ON c.organization_id=a.organization_id AND c.id=a.category_id "
                + "LEFT JOIN organizations owner ON owner.id=a.owner_entity_id "
                + "LEFT JOIN organizations responsible ON responsible.id=a.responsible_entity_id "
                + f"WHERE {where} ORDER BY {sort_column} {sort_direction},a.id "
                "LIMIT :limit OFFSET :skip"
            ),
            params,
        )).mappings().all()

        categories = (await self.session.execute(text(
            "SELECT c.id,c.category_code,c.name_ar AS category_name "
            "FROM eq_categories c WHERE c.organization_id=:org AND c.deleted_at IS NULL "
            "ORDER BY c.category_code"
        ), {"org": org})).mappings().all()
        responsible_entities = (await self.session.execute(text(
            "SELECT DISTINCT a.responsible_entity_id AS id,o.name "
            "FROM eq_assets a JOIN organizations o ON o.id=a.responsible_entity_id "
            "WHERE a.organization_id=:org AND a.deleted_at IS NULL "
            "AND a.responsible_entity_id IS NOT NULL ORDER BY o.name"
        ), {"org": org})).mappings().all()
        locations = (await self.session.execute(text(
            "SELECT DISTINCT current_location FROM eq_assets "
            "WHERE organization_id=:org AND deleted_at IS NULL "
            "AND current_location IS NOT NULL AND current_location<>'' ORDER BY current_location"
        ), {"org": org})).scalars().all()
        visibility = {
            "assignments": can_view_assignments,
            "inspection_blockers": can_view_inspection_blocks,
            "maintenance_blockers": can_view_maintenance_blocks,
        }
        items = [_parse_json(row, ("specifications",)) for row in rows]
        for item in items:
            item["metadata_visibility"] = visibility
        return {
            "items": items,
            "total": count,
            "skip": skip,
            "limit": limit,
            "metadata_visibility": visibility,
            "filter_options": {
                "categories": [dict(row) for row in categories],
                "responsible_entities": [dict(row) for row in responsible_entities],
                "locations": list(locations),
            },
        }

    async def _asset(self, identifier, permission):
        require(self.request, permission)
        row = (await self.session.execute(
            text("SELECT " + ",".join(ASSET_COLUMNS) + " FROM eq_assets WHERE id=:id AND deleted_at IS NULL"),
            {"id": _hex(identifier)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment record unavailable")
        await self._visible_org(row["organization_id"], permission)
        return _parse_json(row, ("specifications",))

    async def _asset_operational_metadata(self, asset):
        visibility = {
            "assignments": self._has_organization_permission("equipment.assignments.view"),
            "inspection_blockers": self._has_organization_permission(
                "equipment.inspections.view"
            ),
            "maintenance_blockers": self._has_organization_permission(
                "equipment.maintenance.view"
            ),
        }
        metadata = {"metadata_visibility": visibility}
        if visibility["assignments"]:
            metadata["assignment_status"] = await self.session.scalar(
                text(
                    "SELECT x.status FROM eq_assignments x WHERE x.organization_id=:org "
                    "AND x.asset_id=:asset AND x.status IN ('approved','dispatched','active','suspended') "
                    "AND x.planned_start_at<=:now AND x.planned_end_at>:now "
                    "ORDER BY CASE x.status WHEN 'active' THEN 0 WHEN 'suspended' THEN 1 "
                    "WHEN 'dispatched' THEN 2 ELSE 3 END,x.planned_start_at DESC LIMIT 1"
                ),
                {"org": asset["organization_id"], "asset": asset["id"], "now": _now()},
            )
        if visibility["inspection_blockers"]:
            reasons = (await self.session.execute(
                text(
                    "SELECT block_reason_code FROM eq_inspections WHERE organization_id=:org "
                    "AND asset_id=:asset AND block_status='active' AND block_reason_code IS NOT NULL"
                ),
                {"org": asset["organization_id"], "asset": asset["id"]},
            )).scalars().all()
            metadata["inspection_blocker_reasons"] = ",".join(reasons)
        if visibility["maintenance_blockers"]:
            reasons = (await self.session.execute(
                text(
                    "SELECT block_reason_code FROM eq_maintenance_orders WHERE organization_id=:org "
                    "AND asset_id=:asset AND block_status='active' AND block_reason_code IS NOT NULL"
                ),
                {"org": asset["organization_id"], "asset": asset["id"]},
            )).scalars().all()
            metadata["maintenance_blocker_reasons"] = ",".join(reasons)
        return metadata

    async def get_asset(self, identifier):
        asset = await self._asset(identifier, "equipment.assets.view")
        display = (await self.session.execute(
            text(
                "SELECT c.category_code,c.name_ar AS category_name,"
                "owner.name AS owner_entity_name,responsible.name AS responsible_entity_name "
                "FROM eq_assets a JOIN eq_categories c "
                "ON c.organization_id=a.organization_id AND c.id=a.category_id "
                "LEFT JOIN organizations owner ON owner.id=a.owner_entity_id "
                "LEFT JOIN organizations responsible ON responsible.id=a.responsible_entity_id "
                "WHERE a.id=:id AND a.organization_id=:org"
            ),
            {"id": _hex(identifier), "org": asset["organization_id"]},
        )).mappings().one()
        asset.update(dict(display))
        asset.update(await self._asset_operational_metadata(asset))
        return asset

    async def create_asset(self, payload, organization_id=None):
        permission = "equipment.assets.manage"
        require(self.request, permission)
        values = payload.model_dump(mode="json")
        org = await self._organization(organization_id, permission, create=True)
        category_id = await self._entity_category(values.pop("category_id"), org, "category_id", active=True)
        category = (await self.session.execute(
            text("SELECT meter_type,meter_unit FROM eq_categories WHERE id=:id AND organization_id=:org"),
            {"id": category_id, "org": org},
        )).mappings().one()
        if category["meter_type"] == "none" and values["meter_initial"] is not None:
            raise HTTPException(422, "This category does not use a meter")
        owner = await self._entity_in_organization(values.get("owner_entity_id"), org, "owner_entity_id")
        responsible = await self._entity_in_organization(
            values.get("responsible_entity_id") or org, org, "responsible_entity_id"
        )
        values["owner_entity_id"] = owner
        values["responsible_entity_id"] = responsible
        if values.get("currency_id"):
            # Currency identifiers are owned by Core; validate existence without creating a local copy.
            currency = await self.session.scalar(
                text("SELECT 1 FROM core_currencies WHERE replace(id,'-','')=:id AND is_active=1"),
                {"id": _hex(values["currency_id"])},
            )
            if not currency:
                raise HTTPException(422, "Unknown currency")
            values["currency_id"] = _hex(values["currency_id"])
        initial = values.pop("meter_initial")
        meter = str(initial) if initial is not None else None
        now, identifier, actor = _now(), uuid4().hex, self.request.state.user_id.hex
        record = {
            "id": identifier, "organization_id": org, "category_id": category_id, **values,
            "meter_initial": meter, "meter_latest": meter, "meter_last_at": now if meter is not None else None,
            "meter_type_locked": category["meter_type"], "meter_unit_locked": category["meter_unit"],
            "meter_generation": 1, "meter_normalized_latest": meter,
            "technical_status": "unknown", "readiness_projection_version": 1,
            "acquisition_value": str(Decimal(values["acquisition_value"])) if values.get("acquisition_value") is not None else None,
            "specifications": json.dumps(values["specifications"], ensure_ascii=False, separators=(",", ":")),
            "acquisition_date": str(values["acquisition_date"]) if values.get("acquisition_date") else None,
            "created_at": now, "updated_at": now, "created_by": actor, "updated_by": actor, "version": 1,
        }
        try:
            await self._insert("eq_assets", ASSET_COLUMNS, record)
        except IntegrityError:
            raise HTTPException(409, "Asset code or serial number already exists in this organization") from None
        self._audit("equipment.asset", identifier, new={"asset_code": record["asset_code"], "category_id": category_id})
        return await self._asset(identifier, permission)

    async def update_asset(self, identifier, payload):
        permission = "equipment.assets.manage"
        require(self.request, permission)
        current = await self._asset(identifier, permission)
        values = payload.model_dump(mode="json", exclude_unset=True)
        expected_version = values.pop("version")
        if not values:
            raise HTTPException(422, "At least one editable field is required")
        owner = await self._entity_in_organization(values.get("owner_entity_id"), current["organization_id"], "owner_entity_id") if "owner_entity_id" in values else None
        responsible = await self._entity_in_organization(values.get("responsible_entity_id"), current["organization_id"], "responsible_entity_id") if "responsible_entity_id" in values else None
        if "owner_entity_id" in values:
            values["owner_entity_id"] = owner
        if "responsible_entity_id" in values:
            values["responsible_entity_id"] = responsible
        if "currency_id" in values and values["currency_id"]:
            currency = await self.session.scalar(
                text("SELECT 1 FROM core_currencies WHERE replace(id,'-','')=:id AND is_active=1"),
                {"id": _hex(values["currency_id"])},
            )
            if not currency:
                raise HTTPException(422, "Unknown currency")
            values["currency_id"] = _hex(values["currency_id"])
        effective_value = values.get("acquisition_value", current["acquisition_value"])
        effective_currency = values.get("currency_id", current["currency_id"])
        if effective_value is not None and effective_currency is None:
            raise HTTPException(422, "currency_id is required when acquisition_value is provided")
        if "specifications" in values and values["specifications"] is not None:
            values["specifications"] = json.dumps(values["specifications"], ensure_ascii=False, separators=(",", ":"))
        if values.get("acquisition_value") is not None:
            values["acquisition_value"] = str(Decimal(values["acquisition_value"]))
        actor, now = self.request.state.user_id.hex, _now()
        values.update(updated_at=now, updated_by=actor, version=expected_version + 1)
        assignments = ",".join(f"{column}=:{column}" for column in values)
        values.update(id=current["id"], organization_id=current["organization_id"], expected_version=expected_version)
        try:
            result = await self.session.execute(
                text(f"UPDATE eq_assets SET {assignments} WHERE id=:id AND organization_id=:organization_id AND version=:expected_version AND deleted_at IS NULL"),
                values,
            )
        except IntegrityError:
            raise HTTPException(409, "Asset code or serial number already exists in this organization") from None
        if result.rowcount != 1:
            raise HTTPException(409, "Equipment record changed; reload before editing")
        self._audit("equipment.asset", current["id"], old={"version": expected_version}, new={"version": expected_version + 1})
        return await self._asset(current["id"], permission)

    async def dashboard(self, organization_id=None):
        permission = "equipment.assets.view"
        require(self.request, permission)
        org = await self._organization(organization_id, permission)
        counts = (await self.session.execute(
            text("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN lifecycle_status='in_service' THEN 1 ELSE 0 END),0) AS in_service, "
                 "COALESCE(SUM(CASE WHEN lifecycle_status IN ('retired','disposed') THEN 1 ELSE 0 END),0) AS out_of_service "
                 "FROM eq_assets WHERE organization_id=:org AND deleted_at IS NULL"),
            {"org": org},
        )).mappings().one()
        return {"assets": dict(counts), "readiness": "not_evaluated"}

    async def _insert(self, table, columns, values):
        names = ",".join(columns)
        binds = ",".join(f":{column}" for column in columns)
        await self.session.execute(text(f"INSERT INTO {table}({names}) VALUES({binds})"), values)

    def _audit(self, entity_type, identifier, old=None, new=None):
        self.request.state.audit_details = {
            "entity_type": entity_type, "entity_id": identifier, "old": old, "new": new,
            "summary": f"{entity_type} registry change",
        }
