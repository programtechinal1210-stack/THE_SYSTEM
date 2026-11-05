from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core import soft_delete
from core import recycle_policy
from core.access import require
from infrastructure.database.db_context import get_session

router = APIRouter()


@router.get("/api/v1/recycle")
async def list_bin(request: Request, entity_type: Optional[str] = Query(None),
                   skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
                   session=Depends(get_session, scope="function")):
    require(request, "core.recycle.view")
    return {"items": await recycle_policy.list_visible(session, request, entity_type, skip, limit)}


@router.post("/api/v1/recycle/{bin_id}/restore")
async def restore_bin(bin_id: str, request: Request,
                      session=Depends(get_session, scope="function")):
    require(request, "core.recycle.manage")
    await recycle_policy.mutate(session, request, bin_id, 'restore')
    return {"restored": True, "bin_id": bin_id}


@router.delete("/api/v1/recycle/{bin_id}")
async def purge_bin(bin_id: str, request: Request,
                    session=Depends(get_session, scope="function")):
    require(request, "core.recycle.manage")
    await recycle_policy.mutate(session, request, bin_id, 'purge')
    return {"purged": True, "bin_id": bin_id}
