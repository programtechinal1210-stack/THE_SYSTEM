"""Scheduling Actual read projection; no Forecast or execution writes."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from infrastructure.database.db_context import get_session
from ..application.actual_read_adapter import ActualReadAdapter


router = APIRouter(prefix="/api/v1/pm", tags=["PM scheduling Actual adapter"])
Session = Depends(get_session, scope="function")


@router.get("/projects/{project_id}/schedule-actual")
async def schedule_actual(project_id: UUID, request: Request,
                          actual_as_of: datetime = Query(...), session=Session):
    return await ActualReadAdapter(session, request).read(project_id.hex, actual_as_of)
