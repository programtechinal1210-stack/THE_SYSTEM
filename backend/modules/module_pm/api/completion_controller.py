from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile

from infrastructure.database.db_context import get_session
from ..application.completion_service import CompletionService
from ..domain.completion import (
    AcceptanceDecision, AttachmentCategory, CloseDecision, IssueCreate, IssueTransition, ReviewDecision,
)

router = APIRouter(prefix='/api/v1/pm/projects/{project_id}/completion', tags=['PM completion'])
Session = Depends(get_session, scope='function')


@router.get('')
async def workspace(project_id: UUID, request: Request, session=Session):
    return await CompletionService(session, request).workspace(project_id.hex)


@router.post('/activities/{activity_id}/review/start')
async def start_review(project_id: UUID, activity_id: UUID, request: Request, session=Session):
    return await CompletionService(session, request).start_review(project_id.hex, activity_id.hex)


@router.post('/activities/{activity_id}/review')
async def review(project_id: UUID, activity_id: UUID, payload: ReviewDecision,
                 request: Request, session=Session):
    return await CompletionService(session, request).review(project_id.hex, activity_id.hex, payload)


@router.post('/activities/{activity_id}/acceptance')
async def accept(project_id: UUID, activity_id: UUID, payload: AcceptanceDecision,
                 request: Request, session=Session):
    return await CompletionService(session, request).accept(project_id.hex, activity_id.hex, payload)


@router.post('/close')
async def close(project_id: UUID, payload: CloseDecision, request: Request, session=Session):
    return await CompletionService(session, request).close_project(project_id.hex, payload)


@router.post('/cases/{case_id}/issues', status_code=201)
async def create_issue(project_id: UUID, case_id: UUID, payload: IssueCreate,
                       request: Request, session=Session):
    return await CompletionService(session, request).create_issue(project_id.hex, case_id.hex, payload)


@router.post('/issues/{issue_id}/{target}')
async def transition_issue(project_id: UUID, issue_id: UUID,
                           target: Literal['in_progress', 'resolved', 'verified'],
                           payload: IssueTransition, request: Request, session=Session):
    return await CompletionService(session, request).transition_issue(
        project_id.hex, issue_id.hex, target, payload)


@router.get('/cases/{case_id}/documents')
async def list_documents(project_id: UUID, case_id: UUID, request: Request, session=Session):
    return await CompletionService(session, request).list_documents(project_id.hex, case_id.hex)


@router.post('/cases/{case_id}/documents', status_code=201)
async def upload_document(project_id: UUID, case_id: UUID, request: Request,
                          category: Literal['review_evidence', 'receipt_minutes',
                                            'closeout_document', 'issue_evidence'],
                          file: UploadFile = File(...), issue_id: Optional[UUID] = None, session=Session):
    return await CompletionService(session, request).upload_document(
        project_id.hex, case_id.hex, category, file, issue_id.hex if issue_id else None)


@router.get('/cases/{case_id}/documents/{attachment_id}')
async def download_document(project_id: UUID, case_id: UUID, attachment_id: UUID,
                           request: Request, session=Session):
    return await CompletionService(session, request).download_document(
        project_id.hex, case_id.hex, attachment_id.hex)
