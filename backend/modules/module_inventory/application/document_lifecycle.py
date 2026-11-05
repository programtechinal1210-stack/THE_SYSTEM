"""Administrative state changes never create or rewrite an economic effect."""
from fastapi import HTTPException
from sqlalchemy import text
from .document_service import DocumentService
from .inventory_service import now
from ..domain.document_policy import DocumentState


class DocumentLifecycle(DocumentService):
    async def decide(self,identifier,action,data):
        permission={'reject':'inventory.documents.approve','cancel':'inventory.documents.create',
                    'revise':'inventory.documents.create','close':'inventory.documents.close'}[action]
        # Acquire the writer before state/scope reads, including closure. The
        # filter leaves posted history untouched while the write statement
        # still serializes SQLite writers, as in the existing posting path.
        await self.session.execute(text("UPDATE inv_documents SET updated_at=updated_at WHERE id=:i AND status NOT IN ('POSTED','CLOSED')"),{'i':identifier})
        row=await self.raw(identifier,permission)
        if action=='cancel' and row.get('source_module'):
            raise HTTPException(409,'EXTERNAL_SOURCE_REQUIRES_OWNER_WORKFLOW')
        actor=self.request.state.user_id.hex
        state=DocumentState(row['created_by'],row['status'],row['approved_by'],row['posted_by'],row['posting_key'])
        try:future=getattr(state,action)(actor)
        except ValueError as exc:raise HTTPException(409,str(exc)) from None
        at=now()
        if action=='close':
            values={'status':'CLOSED','closed_by':actor,'closed_at':at,'closed_reason':data.reason,'updated_at':at}
            updated=await self.session.execute(text("UPDATE inv_documents SET status='CLOSED',closed_by=:actor,closed_at=:at,closed_reason=:reason,updated_at=:at WHERE id=:i AND status='POSTED'"),{'actor':actor,'at':at,'reason':data.reason,'i':identifier})
            if updated.rowcount!=1:raise HTTPException(409,'DOCUMENT_STATE_CHANGED')
        else:
            values={'status':future.status,'decision_action':action,'decision_by':actor,'decision_at':at,'decision_reason':data.reason,'updated_at':at}
            if action=='revise':values.update(submitted_by=None,submitted_at=None,approved_by=None,approved_at=None)
            await self.repo.update('inv_documents',identifier,values)
        self.request.state.audit_details={'entity_type':'inventory.document','entity_id':identifier,'old':row,'new':values}
        return {'id':identifier,**values}
