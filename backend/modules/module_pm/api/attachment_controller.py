import hashlib
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Request,Response,UploadFile,File,HTTPException
from sqlalchemy import text
from infrastructure.database.db_context import get_session
from ..application.planning_service import PlanningService,now

router=APIRouter(prefix='/api/v1/pm/projects',tags=['PM attachments'])
Session=Depends(get_session,scope='function')
FIELDS='id,filename,content_type,size,sha256,created_by,created_at'

@router.get('/{project_id}/activities/{activity_id}/attachments')
async def listing(project_id:UUID,activity_id:UUID,request:Request,session=Session):
    await PlanningService(session,request).entity('activities',project_id.hex,activity_id.hex)
    rows=(await session.execute(text(f'SELECT {FIELDS} FROM pm_activity_attachments WHERE project_id=:p AND activity_id=:a ORDER BY created_at'),{'p':project_id.hex,'a':activity_id.hex})).mappings()
    return {'items':[dict(r) for r in rows]}

@router.post('/{project_id}/activities/{activity_id}/attachments',status_code=201)
async def upload(project_id:UUID,activity_id:UUID,request:Request,file:UploadFile=File(...),session=Session):
    service=PlanningService(session,request)
    await service.entity('activities',project_id.hex,activity_id.hex,'update')
    data=await file.read(5242881)
    if not data or len(data)>5242880:raise HTTPException(422,'حجم الملف المسموح: أكبر من صفر وحتى 5 MB')
    filename=PurePosixPath((file.filename or '').replace('\\','/')).name
    if not filename or len(filename)>200 or any(ord(c)<32 for c in filename):raise HTTPException(422,'اسم الملف غير صالح')
    suffix=PurePosixPath(filename).suffix.lower()
    mime=None
    if suffix=='.pdf' and data.startswith(b'%PDF-'):mime='application/pdf'
    elif suffix=='.png' and data.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
    elif suffix in ('.jpg','.jpeg') and data.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
    elif suffix in ('.txt','.csv'):
        try:
            data.decode('utf-8-sig')
            if b'\0' not in data:mime='text/plain'
        except UnicodeDecodeError:pass
    if not mime:raise HTTPException(422,'الأنواع المقبولة: PDF وPNG وJPEG ونص UTF-8؛ تحقق من محتوى الملف')
    metadata={'id':uuid4().hex,'project_id':project_id.hex,'activity_id':activity_id.hex,
              'filename':filename,'content_type':mime,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),
              'created_by':request.state.user_id.hex,'created_at':now()}
    await session.execute(text('INSERT INTO pm_activity_attachments ('+','.join(metadata)+',content) VALUES ('+','.join(':'+k for k in metadata)+',:content)'),dict(metadata,content=data))
    service.audit('attachments',metadata['id'],None,metadata)
    return metadata

@router.get('/{project_id}/activities/{activity_id}/attachments/{attachment_id}')
async def download(project_id:UUID,activity_id:UUID,attachment_id:UUID,request:Request,session=Session):
    await PlanningService(session,request).entity('activities',project_id.hex,activity_id.hex)
    row=(await session.execute(text('SELECT filename,content_type,content FROM pm_activity_attachments WHERE id=:id AND project_id=:p AND activity_id=:a'),{'id':attachment_id.hex,'p':project_id.hex,'a':activity_id.hex})).mappings().first()
    if not row:raise HTTPException(404,'المرفق غير متاح')
    return Response(row['content'],media_type=row['content_type'],headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['filename'],safe=''),
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
