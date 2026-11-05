"""Read-only EMO analytics derived from approved operational and Inventory records."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import text

from core.access import allowed, require
from modules.module_inventory.application.posting_access import warehouse
from .registry_service import EquipmentRegistryService, _hex


class EquipmentReportingService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    async def analytics(self, organization_id, start_date, end_date, asset_id=None):
        require(self.request, "equipment.reports.view")
        if start_date > end_date:
            raise HTTPException(422, "Report start_date must not follow end_date")
        org = await self.registry._organization(organization_id, "equipment.reports.view")
        parameters = {
            "org": org, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        }
        all_assets = (await self.session.execute(text(
            "SELECT a.id,a.asset_code,a.asset_name,a.category_id,c.category_code,c.name_ar AS category_name,"
            "a.meter_type_locked,a.meter_unit_locked "
            "FROM eq_assets a JOIN eq_categories c ON c.organization_id=a.organization_id "
            "AND c.id=a.category_id WHERE a.organization_id=:org AND a.deleted_at IS NULL"
            " ORDER BY a.asset_code,a.id"
        ), parameters)).mappings().all()
        assets = (
            [row for row in all_assets if row["id"] == _hex(asset_id)]
            if asset_id else all_assets
        )
        if asset_id and not assets:
            raise HTTPException(404, "Equipment asset unavailable")
        asset_options = [
            {"id": row["id"], "asset_code": row["asset_code"], "asset_name": row["asset_name"]}
            for row in all_assets
        ]

        rows = {asset["id"]: {
            **dict(asset), "verified_operations": 0, "working_minutes": 0,
            "idle_minutes": 0, "downtime_minutes": 0, "fuel_events": 0,
            "parts_installed": 0, "parts_removed": 0,
        } for asset in assets}
        if not rows:
            has_cost_permission = allowed(self.request, "equipment.costs.view")
            coverage = ({
                "status": "partial", "currency_conversion": "not_applied",
                "maintenance_costs": "not_recorded", "unpriced_fuel_events": 0,
                "inventory_warehouse_scope_limited": False,
            } if has_cost_permission else None)
            return self._result(
                org, start_date, end_date, rows, [], [], [],
                [] if has_cost_permission else None, coverage, asset_options,
            )

        ids = tuple(rows)
        binds = {f"a{i}": value for i, value in enumerate(ids)}
        in_clause = ",".join(f":a{i}" for i in range(len(ids)))
        operations = (await self.session.execute(text(
            "SELECT asset_id,COUNT(*) AS operation_count,COALESCE(SUM(working_minutes),0) AS working_minutes,"
            "COALESCE(SUM(idle_minutes),0) AS idle_minutes,COALESCE(SUM(downtime_minutes),0) AS downtime_minutes "
            "FROM eq_operation_logs WHERE organization_id=:org AND asset_id IN (" + in_clause + ") "
            "AND status='verified' AND substr(started_at,1,10) BETWEEN :start_date AND :end_date "
            "GROUP BY asset_id"
        ), {**parameters, **binds})).mappings().all()
        for item in operations:
            rows[item["asset_id"]].update({
                "verified_operations": item["operation_count"],
                "working_minutes": item["working_minutes"],
                "idle_minutes": item["idle_minutes"],
                "downtime_minutes": item["downtime_minutes"],
            })

        fuels = (await self.session.execute(text(
            "SELECT asset_id,event_type,energy_type,unit,COUNT(*) AS event_count,"
            "COALESCE(SUM(CAST(quantity AS NUMERIC)),0) AS quantity "
            "FROM eq_fuel_events WHERE organization_id=:org AND asset_id IN (" + in_clause + ") "
            "AND status='posted' AND substr(event_at,1,10) BETWEEN :start_date AND :end_date "
            "GROUP BY asset_id,event_type,energy_type,unit ORDER BY asset_id,energy_type,unit,event_type"
        ), {**parameters, **binds})).mappings().all()
        fuel_rows = []
        for item in fuels:
            rows[item["asset_id"]]["fuel_events"] += item["event_count"]
            fuel_rows.append(dict(item))

        parts = (await self.session.execute(text(
            "SELECT p.asset_id,p.lifecycle_status,COUNT(*) AS part_count "
            "FROM eq_part_lifecycles p WHERE p.organization_id=:org AND p.asset_id IN (" + in_clause + ") "
            "AND ((p.lifecycle_status='installed' AND substr(p.installed_at,1,10) BETWEEN :start_date AND :end_date) "
            "OR (p.lifecycle_status='removed' AND substr(p.removed_at,1,10) BETWEEN :start_date AND :end_date)) "
            "GROUP BY p.asset_id,p.lifecycle_status ORDER BY p.asset_id,p.lifecycle_status"
        ), {**parameters, **binds})).mappings().all()
        part_rows = []
        for item in parts:
            rows[item["asset_id"]]["parts_installed" if item["lifecycle_status"] == "installed" else "parts_removed"] = item["part_count"]
            part_rows.append(dict(item))

        cost_rows = None
        cost_coverage = None
        if allowed(self.request, "equipment.costs.view"):
            cost_rows, cost_coverage = await self._inventory_costs(
                org, ids, binds, in_clause, parameters
            )

        groups = defaultdict(lambda: {
            "category_code": "", "category_name": "", "meter_type": "", "meter_unit": "",
            "asset_count": 0, "verified_operations": 0, "working_minutes": 0,
        })
        for row in rows.values():
            key = (row["category_id"], row["meter_type_locked"], row["meter_unit_locked"])
            group = groups[key]
            group.update({
                "category_code": row["category_code"], "category_name": row["category_name"],
                "meter_type": row["meter_type_locked"], "meter_unit": row["meter_unit_locked"],
            })
            group["asset_count"] += 1
            group["verified_operations"] += row["verified_operations"]
            group["working_minutes"] += row["working_minutes"]
        category_rows = list(groups.values())

        return self._result(
            org, start_date, end_date, rows, fuel_rows, part_rows,
            category_rows, cost_rows, cost_coverage, asset_options,
        )

    async def _inventory_costs(self, org, ids, binds, in_clause, parameters):
        if not allowed(self.request, "inventory.documents.view"):
            return [], {
                "status": "scope_limited", "currency_conversion": "not_applied",
                "maintenance_costs": "not_recorded", "unpriced_fuel_events": None,
            }
        rows = (await self.session.execute(text(
            "SELECT * FROM ("
            " SELECT f.asset_id,c.code AS currency,'fuel_issue' AS cost_type,l.amount_valuation,"
            " d.warehouse_id FROM inv_effective_documents d JOIN inv_document_lines l ON l.document_id=d.id "
            " JOIN eq_fuel_events f ON d.source_id=f.id AND d.source_type='fuel_event' "
            " JOIN core_legal_entities le ON le.id=d.legal_entity_id "
            " JOIN core_currencies c ON c.id=le.valuation_currency_id "
            " WHERE d.organization_id=:org AND d.source_module='equipment' AND d.document_type='ISSUE_DIRECT' "
            " AND d.status IN ('POSTED','CLOSED') AND f.asset_id IN (" + in_clause + ") "
            " AND d.document_date BETWEEN :start_date AND :end_date"
            " UNION ALL"
            " SELECT f.asset_id,c.code,'fuel_return',l.amount_valuation,d.warehouse_id "
            " FROM inv_effective_documents d JOIN inv_document_lines l ON l.document_id=d.id "
            " JOIN eq_fuel_events f ON d.source_id=f.id AND d.source_type='fuel_return_event' "
            " JOIN core_legal_entities le ON le.id=d.legal_entity_id "
            " JOIN core_currencies c ON c.id=le.valuation_currency_id "
            " WHERE d.organization_id=:org AND d.source_module='equipment' AND d.document_type='RECEIPT' "
            " AND d.status IN ('POSTED','CLOSED') AND f.asset_id IN (" + in_clause + ") "
            " AND d.document_date BETWEEN :start_date AND :end_date"
            " UNION ALL"
            " SELECT p.asset_id,c.code,'part_issue',l.amount_valuation,d.warehouse_id "
            " FROM eq_part_lifecycles p JOIN inv_effective_documents d ON d.id=p.installation_inventory_document_id "
            " JOIN inv_document_lines l ON l.document_id=d.id JOIN core_legal_entities le ON le.id=d.legal_entity_id "
            " JOIN core_currencies c ON c.id=le.valuation_currency_id "
            " WHERE p.organization_id=:org AND p.asset_id IN (" + in_clause + ") AND d.status IN ('POSTED','CLOSED') "
            " AND d.document_date BETWEEN :start_date AND :end_date"
            " UNION ALL"
            " SELECT p.asset_id,c.code,'part_return',l.amount_valuation,d.warehouse_id "
            " FROM eq_part_lifecycles p JOIN inv_effective_documents d ON d.id=p.removal_inventory_document_id "
            " JOIN inv_document_lines l ON l.document_id=d.id JOIN core_legal_entities le ON le.id=d.legal_entity_id "
            " JOIN core_currencies c ON c.id=le.valuation_currency_id "
            " WHERE p.organization_id=:org AND p.asset_id IN (" + in_clause + ") AND d.status IN ('POSTED','CLOSED') "
            " AND d.document_date BETWEEN :start_date AND :end_date"
            ") ORDER BY asset_id,currency,cost_type"
        ), {**parameters, **binds})).mappings().all()
        accessible_warehouses = set()
        inaccessible = False
        for item in rows:
            warehouse_id = item["warehouse_id"]
            if warehouse_id in accessible_warehouses:
                continue
            try:
                await warehouse(
                    self.session, self.request, warehouse_id, "inventory.documents.view"
                )
            except HTTPException as exc:
                if exc.status_code not in (403, 404):
                    raise
                inaccessible = True
                continue
            accessible_warehouses.add(warehouse_id)
        totals = defaultdict(lambda: {
            "asset_id": "", "currency": "", "fuel_issue_value": Decimal(0),
            "fuel_return_value": Decimal(0), "part_issue_value": Decimal(0),
            "part_return_value": Decimal(0), "net_inventory_value": Decimal(0),
        })
        for item in rows:
            if item["warehouse_id"] not in accessible_warehouses:
                continue
            key = (item["asset_id"], item["currency"])
            total = totals[key]
            total["asset_id"], total["currency"] = key
            try:
                amount = Decimal(item["amount_valuation"])
            except (InvalidOperation, TypeError, ValueError):
                raise HTTPException(409, "Stored Inventory valuation is invalid") from None
            target = item["cost_type"] + "_value"
            total[target] += amount
            total["net_inventory_value"] += amount if item["cost_type"] in ("fuel_issue", "part_issue") else -amount

        unpriced = None
        if not inaccessible:
            unpriced = await self.session.scalar(text(
                "SELECT COUNT(*) FROM eq_fuel_events f WHERE f.organization_id=:org AND f.asset_id IN ("
                + in_clause + ") AND f.status='posted' AND f.unit_cost IS NULL "
                "AND substr(f.event_at,1,10) BETWEEN :start_date AND :end_date "
                "AND NOT EXISTS (SELECT 1 FROM inv_documents d WHERE d.organization_id=f.organization_id "
                "AND d.source_module='equipment' AND d.source_type='fuel_event' "
                "AND d.source_id=f.id AND d.status IN ('POSTED','CLOSED'))"
            ), {**parameters, **binds})
        return [
            {key: str(value) if isinstance(value, Decimal) else value for key, value in row.items()}
            for row in totals.values()
        ], {
            "status": "partial",
            "currency_conversion": "not_applied",
            "maintenance_costs": "not_recorded",
            "unpriced_fuel_events": int(unpriced or 0) if unpriced is not None else None,
            "inventory_warehouse_scope_limited": inaccessible,
        }

    @staticmethod
    def _result(
        org, start_date, end_date, assets, fuels, parts, categories,
        costs, cost_coverage, asset_options,
    ):
        asset_rows = list(assets.values())
        working_minutes = sum(row["working_minutes"] for row in asset_rows)
        result = {
            "organization_id": org, "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "summary": {
                "asset_count": len(asset_rows),
                "verified_operations": sum(row["verified_operations"] for row in asset_rows),
                "working_minutes": working_minutes,
                "working_hours": str((Decimal(working_minutes) / Decimal(60)).quantize(Decimal("0.01"))),
                "fuel_events": sum(row["fuel_events"] for row in asset_rows),
                "parts_installed": sum(row["parts_installed"] for row in asset_rows),
                "parts_removed": sum(row["parts_removed"] for row in asset_rows),
            },
            "assets": asset_rows, "fuel": fuels, "parts": parts,
            "asset_options": asset_options,
            "category_comparison": categories,
            "costs": costs,
            "cost_coverage": cost_coverage,
            "insights": [
                "الصرف المخزني لا يساوي الاستهلاك الفعلي؛ يعرض كل منهما منفصلاً.",
                "لا تجمع العملات المختلفة ولا تعرض تكلفة الساعة عندما لا تتوفر تكلفة فترة متكاملة.",
                "قيم الوقود والقطع هنا مشتقة من مستندات Inventory المرحّلة فقط؛ تكاليف الصيانة والعمالة والإيجار غير مسجلة في مصادر EMO الحالية.",
            ],
        }
        return result

    async def export_xlsx(self, organization_id, start_date, end_date, asset_id=None):
        require(self.request, "equipment.reports.export")
        report = await self.analytics(organization_id, start_date, end_date, asset_id)
        workbook = Workbook()
        summary = workbook.active
        summary.title = "الملخص"
        self._sheet(summary, ["المؤشر", "القيمة"], [
            ["المؤسسة", report["organization_id"]],
            ["من تاريخ", report["start_date"]],
            ["إلى تاريخ", report["end_date"]],
            *[[key, value] for key, value in report["summary"].items()],
        ])
        assets = workbook.create_sheet("المعدات")
        self._sheet(assets, [
            "رمز المعدة", "اسم المعدة", "التصنيف", "نوع العداد", "وحدة العداد",
            "عمليات متحققة", "دقائق العمل", "دقائق الخمول", "دقائق التوقف",
        ], [[
            row["asset_code"], row["asset_name"], row["category_name"],
            row["meter_type_locked"], row["meter_unit_locked"],
            row["verified_operations"], row["working_minutes"],
            row["idle_minutes"], row["downtime_minutes"],
        ] for row in report["assets"]])
        fuel = workbook.create_sheet("الوقود")
        self._sheet(fuel, ["المعدة", "نوع الحركة", "الطاقة", "الوحدة", "عدد الحركات", "الكمية"], [[
            item["asset_id"], item["event_type"], item["energy_type"], item["unit"],
            item["event_count"], item["quantity"],
        ] for item in report["fuel"]])
        if report["costs"] is not None:
            costs = workbook.create_sheet("تكاليف Inventory")
            self._sheet(costs, [
                "المعدة", "العملة", "قيمة صرف الوقود", "قيمة إرجاع الوقود",
                "قيمة صرف القطع", "قيمة إرجاع القطع", "صافي قيمة حركة Inventory",
            ], [[
                row["asset_id"], row["currency"], row["fuel_issue_value"],
                row["fuel_return_value"], row["part_issue_value"],
                row["part_return_value"], row["net_inventory_value"],
            ] for row in report["costs"]])
        parts = workbook.create_sheet("القطع")
        self._sheet(parts, ["المعدة", "الحالة", "عدد القطع"], [[
            item["asset_id"], item["lifecycle_status"], item["part_count"],
        ] for item in report["parts"]])
        output = BytesIO()
        workbook.save(output)
        self.request.state.audit_details = {
            "entity_type": "equipment.report.export",
            "entity_id": org_id_text(organization_id),
            "new": {"start_date": report["start_date"], "end_date": report["end_date"],
                    "asset_id": _hex(asset_id), "costs_included": report["costs"] is not None},
        }
        return output.getvalue()

    @staticmethod
    def _sheet(sheet, headers, rows):
        sheet.append(headers)
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            width = max(12, min(36, max(len(str(cell.value or "")) for cell in column) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width
            for cell in column:
                if isinstance(cell.value, str):
                    cell.data_type = "s"


def org_id_text(value):
    return _hex(value) if value is not None else ""
