"""Document state and segregation rules; no administrator self-approval escape."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class DocumentState:
    creator_id: str
    status: str = 'DRAFT'
    approver_id: str | None = None
    poster_id: str | None = None
    posting_key: str | None = None

    def submit(self, actor_id):
        if self.status != 'DRAFT' or actor_id != self.creator_id:
            raise ValueError('INVALID_STATE_OR_CREATOR')
        return replace(self, status='SUBMITTED')

    def approve(self, actor_id):
        if actor_id == self.creator_id:
            raise ValueError('SELF_APPROVAL_FORBIDDEN')
        if self.status != 'SUBMITTED':
            raise ValueError('INVALID_STATE')
        return replace(self, status='APPROVED', approver_id=actor_id)

    def post(self, actor_id, posting_key):
        if actor_id == self.creator_id:
            raise ValueError('SELF_POSTING_FORBIDDEN')
        if not posting_key or len(posting_key) > 120:
            raise ValueError('INVALID_IDEMPOTENCY_KEY')
        if self.status in ('POSTED','CLOSED') and posting_key == self.posting_key:
            return self
        if self.status != 'APPROVED' or not self.approver_id:
            raise ValueError('INVALID_STATE')
        return replace(self, status='POSTED', poster_id=actor_id, posting_key=posting_key)

    def require_editable(self):
        if self.status != 'DRAFT':
            raise ValueError('DOCUMENT_IMMUTABLE')

    def reject(self, actor_id):
        if actor_id==self.creator_id:raise ValueError('SELF_APPROVAL_FORBIDDEN')
        if self.status!='SUBMITTED':raise ValueError('INVALID_STATE')
        return replace(self,status='REJECTED')

    def cancel(self, actor_id):
        if actor_id!=self.creator_id or self.status not in ('DRAFT','SUBMITTED','APPROVED','REJECTED'):
            raise ValueError('INVALID_STATE_OR_CREATOR')
        return replace(self,status='CANCELLED')

    def revise(self, actor_id):
        if actor_id!=self.creator_id or self.status!='REJECTED':raise ValueError('INVALID_STATE_OR_CREATOR')
        return replace(self,status='DRAFT',approver_id=None)

    def close(self, actor_id):
        if actor_id==self.creator_id:raise ValueError('SELF_CLOSURE_FORBIDDEN')
        if self.status!='POSTED':raise ValueError('INVALID_STATE')
        return replace(self,status='CLOSED')
