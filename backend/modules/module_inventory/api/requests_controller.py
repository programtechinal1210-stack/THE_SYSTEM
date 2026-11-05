from uuid import UUID
from fastapi import APIRouter, Request, Query
from .documents_controller import Session
from ..domain.requests import MaterialRequest, Decision, Reservation
from ..application.request_service import RequestService
from ..application.reservation_service import ReservationService

router=APIRouter(prefix='/api/v1/inventory',tags=['Inventory requests and reservations'])


@router.get('/request-lines')
async def source_lines(organization_id:UUID,request:Request,session=Session):
    service=RequestService(session,request)
    await service.scope(organization_id.hex,'inventory.requests.view')
    return {'items':await service.repo.many("SELECT l.*,r.request_no,i.name_ar FROM inv_request_lines l "
        "JOIN inv_material_requests r ON r.id=l.request_id JOIN inv_items i ON i.id=l.item_id "
        "WHERE r.organization_id=:o AND r.status IN ('APPROVED','PARTIAL') ORDER BY r.created_at DESC,l.id LIMIT 200",o=organization_id.hex)}


@router.get('/requests')
async def listing(organization_id:UUID,request:Request,session=Session,
                  skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),
                  search:str|None=None,status:str|None=None,
                  date_from:str|None=None,date_to:str|None=None,
                  department_id:UUID|None=None):
    return await RequestService(session,request).listing(
        organization_id.hex, skip, limit, search, status, date_from, date_to,
        department_id.hex if department_id else None,
    )


@router.post('/requests',status_code=201)
async def create(data:MaterialRequest,request:Request,session=Session):
    return await RequestService(session,request).save(data)


@router.get('/requests/{identifier}')
async def detail(identifier:UUID,request:Request,session=Session):
    return await RequestService(session,request).detail(identifier.hex)


@router.put('/requests/{identifier}')
async def update(identifier:UUID,data:MaterialRequest,request:Request,session=Session):
    return await RequestService(session,request).save(data,identifier.hex)


@router.post('/requests/{identifier}/{action}')
async def transition(identifier:UUID,action:str,data:Decision,request:Request,session=Session):
    return await RequestService(session,request).transition(identifier.hex,action,data)


@router.get('/reservations')
async def reservations(warehouse_id:UUID,request:Request,session=Session):
    return await ReservationService(session,request).listing(warehouse_id.hex)


@router.post('/reservations',status_code=201)
async def reserve(data:Reservation,request:Request,session=Session):
    return await ReservationService(session,request).create(data)


@router.post('/reservations/{identifier}/release')
async def release(identifier:UUID,request:Request,session=Session):
    return await ReservationService(session,request).release(identifier.hex)


@router.post('/reservations/{identifier}/expire')
async def expire(identifier:UUID,request:Request,session=Session):
    return await ReservationService(session,request).release(identifier.hex,expire=True)
