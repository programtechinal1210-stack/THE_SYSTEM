"""Authenticated metadata only: no project data or business operations."""
from fastapi import APIRouter, Depends, Request
from core.access import require
from .. import VERSION


def require_pm_access(request: Request):
    require(request, "pm.access")


router = APIRouter(prefix="/api/v1/pm", tags=["PM"],
                   dependencies=[Depends(require_pm_access)])


@router.get("/health")
async def health():
    return {"module": "pm", "status": "ready", "version": VERSION}


@router.get("/")
async def home():
    return {"module": "pm", "name": "إدارة المشاريع", "status": "ready", "version": VERSION}
