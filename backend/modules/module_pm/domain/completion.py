"""Completion review, acceptance and close-out input contracts."""
from datetime import date
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ReviewDecision(Input):
    result: Literal['passed', 'requires_treatment']
    notes: Text = ''
    missing_requirement: Text = ''
    corrective_action: Text = ''
    owner_user_id: Optional[UUID] = None
    target_date: Optional[date] = None


class AcceptanceDecision(Input):
    result: Literal['accepted', 'rejected']
    acceptance_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    reference: Text = ''
    notes: Text = ''


class CloseDecision(Input):
    reason: RequiredText


class IssueCreate(Input):
    description: RequiredText
    issue_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    severity: Literal['critical', 'high', 'medium', 'low'] = 'medium'
    blocking: bool = True
    owner_user_id: Optional[UUID] = None
    target_date: Optional[date] = None


class IssueTransition(Input):
    notes: RequiredText


class AttachmentCategory(Input):
    category: Literal['review_evidence', 'receipt_minutes', 'closeout_document', 'issue_evidence']
