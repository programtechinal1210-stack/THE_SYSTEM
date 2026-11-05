from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError

from infrastructure.database.db_context import get_session
from ..application.registry_service import EquipmentRegistryService
from ..application.fuel_service import EquipmentFuelService
from ..application.inventory_mapping_service import EquipmentInventoryMappingService
from ..application.meter_service import EquipmentMeterService
from ..application.operation_service import EquipmentOperationService
from ..application.parts_service import EquipmentPartService
from ..application.reporting_service import EquipmentReportingService
from ..application.safety_service import EquipmentSafetyService
from ..domain.catalog import AssetInput, AssetUpdate, CategoryInput, CategoryUpdate
from ..domain.fuel import FuelEventDecisionInput, FuelEventInput
from ..domain.inventory_mapping import FuelInventoryMappingInput
from ..domain.maintenance import MaintenancePlanInput
from ..domain.meter import MeterCorrectionInput, MeterReadingInput, MeterReplacementInput
from ..domain.operations import (
    OperationFinishInput,
    OperationStartInput,
    SafetyPolicyDecision,
    SafetyPolicyInput,
)
from ..domain.parts import PartInstallInput, PartRemovalInput, PartReplacementInput
from ..domain.safety import (
    AssignmentInput,
    EquipmentRequestInput,
    InspectionInput,
    MaintenanceCompletionInput,
    MaintenanceInput,
    MovementInput,
    MovementReceiptInput,
    RequestDecisionInput,
    SafetyReleaseInput,
)

router = APIRouter(prefix="/api/v1/equipment", tags=["Equipment"])
Session = Depends(get_session, scope="function")


@router.get("/safety-policies")
async def list_safety_policies(
    request: Request, session=Session, organization_id: UUID | None = None
):
    return await EquipmentOperationService(session, request).list_policies(organization_id)


@router.post("/safety-policies", status_code=201)
async def create_safety_policy(request: Request, session=Session):
    payload = _validate(SafetyPolicyInput, await request.json())
    return await EquipmentOperationService(session, request).create_policy(payload)


@router.post("/safety-policies/{policy_id}/approve")
async def approve_safety_policy(policy_id: UUID, request: Request, session=Session):
    payload = _validate(SafetyPolicyDecision, await request.json())
    return await EquipmentOperationService(session, request).decide_policy(
        policy_id, True, payload.decision_authority_ref
    )


@router.post("/safety-policies/{policy_id}/withdraw")
async def withdraw_safety_policy(policy_id: UUID, request: Request, session=Session):
    payload = _validate(SafetyPolicyDecision, await request.json())
    return await EquipmentOperationService(session, request).decide_policy(
        policy_id, False, payload.decision_authority_ref
    )


@router.get("/operations")
async def list_operations(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    asset_id: UUID | None = None,
):
    return await EquipmentOperationService(session, request).list_operations(
        organization_id, asset_id
    )


@router.post("/operations", status_code=201)
async def start_operation(request: Request, session=Session):
    payload = _validate(OperationStartInput, await request.json())
    return await EquipmentOperationService(session, request).start(payload)


@router.post("/operations/{operation_id}/finish")
async def finish_operation(operation_id: UUID, request: Request, session=Session):
    payload = _validate(OperationFinishInput, await request.json())
    return await EquipmentOperationService(session, request).finish(operation_id, payload)


@router.post("/operations/{operation_id}/verify")
async def verify_operation(operation_id: UUID, request: Request, session=Session):
    return await EquipmentOperationService(session, request).verify(operation_id)


@router.get("/inventory/fuel-mappings")
async def list_fuel_inventory_mappings(
    request: Request, session=Session, organization_id: UUID | None = None
):
    return await EquipmentInventoryMappingService(session, request).list(organization_id)


@router.put("/inventory/fuel-mappings/{category_id}/{energy_type}")
async def save_fuel_inventory_mapping(
    category_id: UUID,
    energy_type: str,
    data: FuelInventoryMappingInput,
    request: Request,
    session=Session,
):
    return await EquipmentInventoryMappingService(session, request).save(
        category_id, energy_type, data
    )


def _validate(model, payload):
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


@router.get("/assets/{asset_id}/meter-events")
async def list_meter_events(asset_id: UUID, request: Request, session=Session):
    return await EquipmentMeterService(session, request).list_events(asset_id)


@router.post("/assets/{asset_id}/meter-readings", status_code=201)
async def record_meter_reading(asset_id: UUID, request: Request, session=Session):
    payload = _validate(MeterReadingInput, await request.json())
    return await EquipmentMeterService(session, request).record_reading(asset_id, payload)


@router.post("/assets/{asset_id}/meter-replacements", status_code=201)
async def record_meter_replacement(asset_id: UUID, request: Request, session=Session):
    payload = _validate(MeterReplacementInput, await request.json())
    return await EquipmentMeterService(session, request).record_replacement(asset_id, payload)


@router.post("/assets/{asset_id}/meter-corrections", status_code=201)
async def record_meter_correction(asset_id: UUID, request: Request, session=Session):
    payload = _validate(MeterCorrectionInput, await request.json())
    return await EquipmentMeterService(session, request).record_correction(asset_id, payload)


@router.post("/meter-events/{event_id}/approve")
async def approve_meter_event(event_id: UUID, request: Request, session=Session):
    return await EquipmentMeterService(session, request).approve_event(event_id)


@router.get("/assets/{asset_id}/fuel-events")
async def list_fuel_events(asset_id: UUID, request: Request, session=Session):
    return await EquipmentFuelService(session, request).list_events(asset_id)


@router.get("/assets/{asset_id}/fuel-balance")
async def fuel_balance(asset_id: UUID, request: Request, session=Session):
    return await EquipmentFuelService(session, request).balances(asset_id)


@router.post("/assets/{asset_id}/fuel-events", status_code=201)
async def create_fuel_event(asset_id: UUID, request: Request, session=Session):
    payload = _validate(FuelEventInput, await request.json())
    return await EquipmentFuelService(session, request).create_event(asset_id, payload)


@router.post("/fuel-events/{event_id}/approve")
async def approve_fuel_event(event_id: UUID, request: Request, session=Session):
    payload = _validate(FuelEventDecisionInput, await request.json())
    return await EquipmentFuelService(session, request).decide_event(
        event_id, True, payload.decision_reason
    )


@router.post("/fuel-events/{event_id}/reject")
async def reject_fuel_event(event_id: UUID, request: Request, session=Session):
    payload = _validate(FuelEventDecisionInput, await request.json())
    return await EquipmentFuelService(session, request).decide_event(
        event_id, False, payload.decision_reason
    )


@router.get("/assets/{asset_id}/part-lifecycles")
async def list_part_lifecycles(asset_id: UUID, request: Request, session=Session):
    return await EquipmentPartService(session, request).list_for_asset(asset_id)


@router.post("/assets/{asset_id}/part-lifecycles", status_code=201)
async def install_part(asset_id: UUID, request: Request, session=Session):
    payload = _validate(PartInstallInput, await request.json())
    return await EquipmentPartService(session, request).install(asset_id, payload)


@router.post("/part-lifecycles/{lifecycle_id}/remove")
async def remove_part(lifecycle_id: UUID, request: Request, session=Session):
    payload = _validate(PartRemovalInput, await request.json())
    return await EquipmentPartService(session, request).remove(lifecycle_id, payload)


@router.post("/part-lifecycles/{lifecycle_id}/replace")
async def replace_part(lifecycle_id: UUID, request: Request, session=Session):
    payload = _validate(PartReplacementInput, await request.json())
    return await EquipmentPartService(session, request).replace(lifecycle_id, payload)


@router.get("/")
async def module_health(request: Request, session=Session):
    from core.access import require
    require(request, "equipment.assets.view")
    return {"module": "equipment", "status": "ready", "registry": "available"}


@router.get("/dashboard")
async def dashboard(request: Request, session=Session, organization_id: UUID | None = None):
    return await EquipmentRegistryService(session, request).dashboard(organization_id)


@router.get("/asset-form-options")
async def asset_form_options(
    request: Request, session=Session, organization_id: UUID | None = None
):
    return await EquipmentRegistryService(session, request).asset_form_options(organization_id)


@router.get("/reports/analytics")
async def equipment_analytics(
    request: Request, organization_id: UUID, start_date: date, end_date: date,
    asset_id: UUID | None = None, session=Session,
):
    return await EquipmentReportingService(session, request).analytics(
        organization_id, start_date, end_date, asset_id
    )


@router.get("/reports/analytics.xlsx")
async def equipment_analytics_export(
    request: Request, organization_id: UUID, start_date: date, end_date: date,
    asset_id: UUID | None = None, session=Session,
):
    content = await EquipmentReportingService(session, request).export_xlsx(
        organization_id, start_date, end_date, asset_id
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="equipment-analytics.xlsx"'},
    )


@router.get("/categories")
async def list_categories(request: Request, session=Session, organization_id: UUID | None = None,
                          search: str | None = None, skip: int = Query(0, ge=0),
                          limit: int = Query(100, ge=1, le=200)):
    return await EquipmentRegistryService(session, request).list_categories(organization_id, search, skip, limit)


@router.post("/categories", status_code=201)
async def create_category(request: Request, session=Session, organization_id: UUID | None = None):
    payload = _validate(CategoryInput, await request.json())
    return await EquipmentRegistryService(session, request).create_category(payload, organization_id)


@router.patch("/categories/{category_id}")
async def update_category(category_id: UUID, request: Request, session=Session):
    payload = _validate(CategoryUpdate, await request.json())
    return await EquipmentRegistryService(session, request).update_category(category_id, payload)


@router.get("/assets")
async def list_assets(request: Request, session=Session, organization_id: UUID | None = None,
                      search: str | None = None, skip: int = Query(0, ge=0),
                      limit: int = Query(100, ge=1, le=200), category_id: UUID | None = None,
                      lifecycle_status: Literal["in_service", "suspended", "retired", "disposed"] | None = None,
                      technical_status: Literal["unknown", "unsafe", "maintenance", "out_of_service"] | None = None,
                      responsible_entity_id: UUID | None = None,
                      location: str | None = Query(None, max_length=300),
                      sort_by: Literal[
                          "asset_code", "asset_name", "category_name", "lifecycle_status",
                          "current_location", "created_at",
                      ] = "asset_code",
                      sort_dir: Literal["asc", "desc"] = "asc"):
    return await EquipmentRegistryService(session, request).list_assets(
        organization_id, search, skip, limit, category_id, lifecycle_status,
        technical_status, responsible_entity_id, location, sort_by, sort_dir,
    )


@router.post("/assets", status_code=201)
async def create_asset(request: Request, session=Session, organization_id: UUID | None = None):
    payload = _validate(AssetInput, await request.json())
    return await EquipmentRegistryService(session, request).create_asset(payload, organization_id)


@router.get("/assets/{asset_id}")
async def asset_detail(asset_id: UUID, request: Request, session=Session):
    return await EquipmentRegistryService(session, request).get_asset(asset_id)


@router.patch("/assets/{asset_id}")
async def update_asset(asset_id: UUID, request: Request, session=Session):
    payload = _validate(AssetUpdate, await request.json())
    return await EquipmentRegistryService(session, request).update_asset(asset_id, payload)


@router.post("/assignments", status_code=201)
async def create_assignment(request: Request, session=Session):
    payload = _validate(AssignmentInput, await request.json())
    return await EquipmentSafetyService(session, request).create_assignment(payload)


@router.get("/assignments")
async def list_all_assignments(
    request: Request, session=Session, organization_id: UUID | None = None
):
    return await EquipmentSafetyService(session, request).list_all_assignments(organization_id)


@router.get("/assets/{asset_id}/assignments")
async def list_assignments(asset_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).list_assignments(asset_id)


@router.post("/assignments/{assignment_id}/approve")
async def approve_assignment(assignment_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).approve_assignment(assignment_id)


@router.post("/inspections", status_code=201)
async def create_inspection(request: Request, session=Session):
    payload = _validate(InspectionInput, await request.json())
    return await EquipmentSafetyService(session, request).create_inspection(payload)


@router.get("/inspections")
async def list_inspections(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    asset_id: UUID | None = None,
    status: str | None = None,
):
    return await EquipmentSafetyService(session, request).list_inspections(
        organization_id, asset_id, status
    )


@router.post("/inspections/{inspection_id}/verify")
async def verify_inspection(inspection_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).verify_inspection(inspection_id)


@router.post("/maintenance-orders", status_code=201)
async def create_maintenance_order(request: Request, session=Session):
    payload = _validate(MaintenanceInput, await request.json())
    return await EquipmentSafetyService(session, request).create_maintenance_order(payload)


@router.get("/maintenance-orders")
async def list_maintenance_orders(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    asset_id: UUID | None = None,
    status: str | None = None,
):
    return await EquipmentSafetyService(session, request).list_maintenance_orders(
        organization_id, asset_id, status
    )


@router.post("/maintenance-plans", status_code=201)
async def create_maintenance_plan(request: Request, session=Session):
    payload = _validate(MaintenancePlanInput, await request.json())
    return await EquipmentSafetyService(session, request).create_maintenance_plan(payload)


@router.get("/maintenance-plans")
async def list_maintenance_plans(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    asset_id: UUID | None = None,
    status: str | None = None,
):
    return await EquipmentSafetyService(session, request).list_maintenance_plans(
        organization_id, asset_id, status
    )


@router.get("/maintenance-plans/due")
async def list_due_maintenance_plans(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    asset_id: UUID | None = None,
):
    return await EquipmentSafetyService(session, request).list_due_maintenance_plans(
        organization_id, asset_id
    )


@router.post("/maintenance-plans/{plan_id}/orders", status_code=201)
async def generate_due_maintenance_order(plan_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).generate_due_maintenance_order(plan_id)


@router.post("/maintenance-plans/{plan_id}/pause")
async def pause_maintenance_plan(plan_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).set_maintenance_plan_status(
        plan_id, "paused"
    )


@router.post("/maintenance-plans/{plan_id}/resume")
async def resume_maintenance_plan(plan_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).set_maintenance_plan_status(
        plan_id, "active"
    )


@router.post("/maintenance-orders/{order_id}/complete")
async def complete_maintenance_order(order_id: UUID, request: Request, session=Session):
    payload = _validate(MaintenanceCompletionInput, await request.json())
    return await EquipmentSafetyService(session, request).complete_maintenance(order_id, payload)


@router.post("/inspections/{inspection_id}/release-block")
async def release_inspection_block(inspection_id: UUID, request: Request, session=Session):
    payload = _validate(SafetyReleaseInput, await request.json())
    return await EquipmentSafetyService(session, request).release_inspection_block(inspection_id, payload)


@router.post("/maintenance-orders/{order_id}/release-block")
async def release_maintenance_block(order_id: UUID, request: Request, session=Session):
    payload = _validate(SafetyReleaseInput, await request.json())
    return await EquipmentSafetyService(session, request).release_maintenance_block(order_id, payload)


@router.get("/assets/{asset_id}/readiness")
async def asset_readiness(
    asset_id: UUID,
    request: Request,
    session=Session,
    assignment_id: UUID | None = None,
):
    return await EquipmentSafetyService(session, request).readiness(asset_id, assignment_id)


@router.get("/requests")
async def list_equipment_requests(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    status: str | None = None,
):
    return await EquipmentSafetyService(session, request).list_requests(organization_id, status)


@router.post("/requests", status_code=201)
async def create_equipment_request(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
):
    payload = _validate(EquipmentRequestInput, await request.json())
    return await EquipmentSafetyService(session, request).create_request(payload, organization_id)


@router.post("/requests/{request_id}/approve")
async def approve_equipment_request(request_id: UUID, request: Request, session=Session):
    payload = _validate(RequestDecisionInput, await request.json())
    return await EquipmentSafetyService(session, request).decide_request(
        request_id, "approve", payload.decision_reason
    )


@router.post("/requests/{request_id}/reject")
async def reject_equipment_request(request_id: UUID, request: Request, session=Session):
    payload = _validate(RequestDecisionInput, await request.json())
    return await EquipmentSafetyService(session, request).decide_request(
        request_id, "reject", payload.decision_reason
    )


@router.post("/movements", status_code=201)
async def create_equipment_movement(request: Request, session=Session):
    payload = _validate(MovementInput, await request.json())
    return await EquipmentSafetyService(session, request).create_movement(payload)


@router.get("/assets/{asset_id}/movements")
async def list_equipment_movements(asset_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).list_movements(asset_id)


@router.get("/movements")
async def list_movements(
    request: Request,
    session=Session,
    organization_id: UUID | None = None,
    status: str | None = None,
):
    return await EquipmentSafetyService(session, request).list_movements(
        organization_id=organization_id, status=status
    )


@router.post("/movements/{movement_id}/dispatch")
async def dispatch_equipment_movement(movement_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).dispatch_movement(movement_id)


@router.post("/movements/{movement_id}/receive")
async def receive_equipment_movement(movement_id: UUID, request: Request, session=Session):
    payload = _validate(MovementReceiptInput, await request.json())
    return await EquipmentSafetyService(session, request).receive_movement(movement_id, payload)


@router.post("/movements/{movement_id}/cancel")
async def cancel_equipment_movement(movement_id: UUID, request: Request, session=Session):
    return await EquipmentSafetyService(session, request).cancel_movement(movement_id)
