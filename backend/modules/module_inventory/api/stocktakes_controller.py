from uuid import UUID
from fastapi import APIRouter,Request,Query,HTTPException
from .documents_controller import Session
from ..domain.stocktakes import StocktakeCreate,CountEntry,ObservedCount,CountSettlement
from ..domain.documents import DocumentDecision
from ..application.stocktake_service import StocktakeService
from ..application.count_posting import CountPosting

router=APIRouter(prefix='/api/v1/inventory/stocktakes',tags=['Inventory stocktakes'])


@router.get('')
async def listing(warehouse_id:UUID,request:Request,session=Session,skip:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=200)):
    return await StocktakeService(session,request).list(warehouse_id.hex,skip,limit)


@router.post('',status_code=201)
async def create(data:StocktakeCreate,request:Request,session=Session):
    return await StocktakeService(session,request).create(data)


@router.get('/{identifier}')
async def detail(identifier:UUID,request:Request,session=Session,skip:int=Query(0,ge=0),limit:int=Query(200,ge=1,le=200)):
    return await StocktakeService(session,request).detail(identifier.hex,skip,limit)


@router.get('/{identifier}/actions')
async def actions(identifier:UUID,request:Request,session=Session):
    return await StocktakeService(session,request).actions(identifier.hex)


@router.put('/{identifier}/lines/{line_id}')
async def record(identifier:UUID,line_id:UUID,data:CountEntry,request:Request,session=Session):
    return await StocktakeService(session,request).record(identifier.hex,line_id.hex,data)


@router.post('/{identifier}/lines',status_code=201)
async def observed(identifier:UUID,data:ObservedCount,request:Request,session=Session):
    return await StocktakeService(session,request).observed(identifier.hex,data)


@router.post('/{identifier}/settlement',status_code=201)
async def settlement(identifier:UUID,data:CountSettlement,request:Request,session=Session):
    return await CountPosting(session,request).create(identifier.hex,data)


@router.post('/{identifier}/{action}')
async def decide(identifier:UUID,action:str,data:DocumentDecision,request:Request,session=Session):
    if action not in ('submit','approve','reopen','cancel','confirm-empty'):raise HTTPException(404,'UNKNOWN_STOCKTAKE_ACTION')
    return await StocktakeService(session,request).decide(identifier.hex,action,data)
