"""Inventory source validation backed by immutable EMO operational events."""
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import text
from modules.module_inventory.domain.financial_policy import (
    COST_SCALE,
    money,
    transfer_allocation,
)


async def fuel_return_warehouse(session, organization_id, source_id):
    row = (await session.execute(text(
        "SELECT d.warehouse_id FROM eq_fuel_events e "
        "JOIN inv_documents d ON d.organization_id=e.organization_id "
        "AND d.source_module='equipment' AND d.source_type='fuel_event' "
        "AND d.source_id=e.related_issue_event_id AND d.document_type='ISSUE_DIRECT' "
        "AND d.status IN ('POSTED','CLOSED') "
        "WHERE e.id=:id AND e.organization_id=:org "
        "AND e.event_type='returned' AND e.status='posted' "
        "AND e.related_issue_event_id IS NOT NULL"
    ), {"id": source_id, "org": organization_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "Equipment fuel return source unavailable")
    return row["warehouse_id"]


async def fuel_return_details(session, organization_id, source_id):
    event = (await session.execute(text(
        "SELECT e.id,e.organization_id,e.asset_id,e.event_type,e.energy_type,e.quantity,e.unit,"
        "e.status,e.event_at,e.related_issue_event_id,a.category_id "
        "FROM eq_fuel_events e JOIN eq_assets a "
        "ON a.organization_id=e.organization_id AND a.id=e.asset_id WHERE e.id=:id"
    ), {"id": source_id})).mappings().first()
    if (
        event is None or event["organization_id"] != organization_id
        or event["event_type"] != "returned" or event["status"] != "posted"
        or not event["related_issue_event_id"]
    ):
        raise HTTPException(409, "Approved linked fuel return source required")

    issue = (await session.execute(text(
        "SELECT d.id,d.organization_id,d.warehouse_id,d.legal_entity_id,d.document_date,l.id AS line_id,"
        "l.item_id,l.unit_id,l.base_quantity,l.amount_valuation,i.base_unit_id,u.code AS unit_code,"
        "c.id AS valuation_currency_id,c.code AS valuation_currency "
        "FROM inv_documents d JOIN inv_document_lines l ON l.document_id=d.id "
        "JOIN inv_items i ON i.id=l.item_id JOIN inv_units u ON u.id=i.base_unit_id "
        "JOIN core_legal_entities e ON e.id=d.legal_entity_id "
        "JOIN core_currencies c ON c.id=e.valuation_currency_id "
        "WHERE d.organization_id=:org AND d.source_module='equipment' "
        "AND d.source_type='fuel_event' AND d.source_id=:source "
        "AND d.document_type='ISSUE_DIRECT' AND d.status IN ('POSTED','CLOSED')"
    ), {
        "org": organization_id, "source": event["related_issue_event_id"],
    })).mappings().all()
    if len(issue) != 1:
        raise HTTPException(409, "Posted Inventory issue source unavailable")
    issue = issue[0]
    if (
        issue["unit_code"] != event["unit"]
        or issue["organization_id"] != organization_id
        or issue["legal_entity_id"] is None
        or issue["amount_valuation"] is None
        or event["event_at"][:10] < issue["document_date"]
    ):
        raise HTTPException(409, "Fuel return and original Inventory issue are inconsistent")

    source_event = (await session.execute(text(
        "SELECT organization_id,asset_id,event_type,energy_type,unit,status "
        "FROM eq_fuel_events WHERE id=:id"
    ), {"id": event["related_issue_event_id"]})).mappings().first()
    if (
        source_event is None
        or source_event["organization_id"] != organization_id
        or source_event["asset_id"] != event["asset_id"]
        or source_event["event_type"] != "issued"
        or source_event["energy_type"] != event["energy_type"]
        or source_event["unit"] != event["unit"]
        or source_event["status"] != "posted"
    ):
        raise HTTPException(409, "Fuel return does not match its approved issue event")

    settled_lines = (await session.execute(text(
        "SELECT l.base_quantity,l.amount_valuation "
        "FROM inv_documents d JOIN inv_document_lines l ON l.document_id=d.id "
        "JOIN eq_fuel_events returned ON returned.id=d.source_id "
        "WHERE d.organization_id=:org AND d.source_module='equipment' "
        "AND d.source_type='fuel_return_event' AND d.document_type='RECEIPT' "
        "AND d.status IN ('POSTED','CLOSED') AND returned.related_issue_event_id=:issue"
    ), {
        "org": organization_id, "issue": event["related_issue_event_id"],
    })).mappings().all()
    try:
        settled_quantity = sum(
            (Decimal(line["base_quantity"]) for line in settled_lines), Decimal(0)
        )
        settled_value = sum(
            (Decimal(line["amount_valuation"]) for line in settled_lines), Decimal(0)
        )
        allocated_value = transfer_allocation(
            issue["base_quantity"], issue["amount_valuation"],
            settled_quantity, settled_value, event["quantity"],
        )
        quantity = Decimal(event["quantity"])
        unit_price = (allocated_value / quantity).quantize(COST_SCALE)
        if money(quantity * unit_price) != allocated_value:
            raise ValueError("Historical value cannot be represented exactly")
    except (ValueError, InvalidOperation, TypeError, ArithmeticError):
        raise HTTPException(409, "Fuel return exceeds or cannot reconcile to original Inventory value") from None
    return {
        "event": event,
        "issue": issue,
        "allocated_value": allocated_value,
        "unit_price": unit_price,
    }


async def validate_fuel_issue(
    session, organization_id, source_id, document_type, warehouse_id, lines,
    require_posted,
):
    event = (await session.execute(text(
        "SELECT e.organization_id,e.asset_id,e.event_type,e.energy_type,e.quantity,e.unit,e.status,"
        "a.category_id FROM eq_fuel_events e JOIN eq_assets a "
        "ON a.organization_id=e.organization_id AND a.id=e.asset_id WHERE e.id=:id"
    ), {"id": source_id})).mappings().first()
    if event is None or event["organization_id"] != organization_id:
        raise HTTPException(404, "Equipment fuel source unavailable")
    if event["event_type"] != "issued" or document_type != "ISSUE_DIRECT":
        raise HTTPException(409, "Fuel stock documents require an issued fuel event")
    allowed_statuses = {"posted"} if require_posted else {"draft", "posted"}
    if event["status"] not in allowed_statuses:
        raise HTTPException(409, "Fuel source is not approved for this document transition")
    if len(lines) != 1:
        raise HTTPException(422, "A fuel event must map to exactly one Inventory issue line")

    mapping = (await session.execute(text(
        "SELECT item_id,warehouse_id FROM eq_inventory_fuel_mappings "
        "WHERE organization_id=:org AND category_id=:category AND energy_type=:energy AND is_active=1"
    ), {
        "org": organization_id, "category": event["category_id"],
        "energy": event["energy_type"],
    })).mappings().first()
    if mapping is None:
        raise HTTPException(409, "FUEL_INVENTORY_MAPPING_REQUIRED")
    if mapping["item_id"] != lines[0]["item_id"] or mapping["warehouse_id"] != warehouse_id:
        raise HTTPException(422, "Inventory line and warehouse must match the approved equipment mapping")

    line = lines[0]
    unit = (await session.execute(text(
        "SELECT u.code FROM inv_items i JOIN inv_units u ON u.id=i.base_unit_id "
        "WHERE i.id=:item AND i.organization_id=:org"
    ), {"item": line["item_id"], "org": organization_id})).mappings().first()
    if unit is None or unit["code"] != event["unit"]:
        raise HTTPException(422, "Fuel event and Inventory base units must match exactly")
    try:
        source_quantity = Decimal(event["quantity"])
        inventory_quantity = Decimal(str(line["base_quantity"]))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, "Fuel source or Inventory quantity is invalid") from None
    if source_quantity != inventory_quantity:
        raise HTTPException(422, "Fuel event and Inventory issue quantities must match")


async def validate_fuel_return(
    session, organization_id, source_id, document_type, warehouse_id, lines,
    require_posted,
):
    if document_type != "RECEIPT":
        raise HTTPException(409, "Fuel return source requires an Inventory receipt")
    details = await fuel_return_details(session, organization_id, source_id)
    if len(lines) != 1:
        raise HTTPException(422, "A fuel return must map to exactly one Inventory receipt line")
    event, issue, line = details["event"], details["issue"], lines[0]
    try:
        returned_quantity = Decimal(event["quantity"])
        inventory_quantity = Decimal(str(line["base_quantity"]))
        returned_price = Decimal(str(line["original_unit_price"]))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, "Fuel return or Inventory receipt values are invalid") from None
    if (
        issue["warehouse_id"] != warehouse_id
        or issue["item_id"] != line["item_id"]
        or issue["base_unit_id"] != line["unit_id"]
        or returned_quantity != inventory_quantity
        or returned_price != details["unit_price"]
        or line["transaction_currency_id"] != issue["valuation_currency_id"]
    ):
        raise HTTPException(422, "Fuel return receipt must match the original issue item, warehouse, unit, quantity and historical value")
