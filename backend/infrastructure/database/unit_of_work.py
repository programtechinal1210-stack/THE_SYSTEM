from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Optional
from infrastructure.database.base_repository import BaseRepository

T = TypeVar('T')

class UnitOfWork:
  #  \"\"\"وحدة العمل - إدارة المعاملات\"\"\"
    
    def __init__(self, session: Session):
        self.session = session
        self._repositories = {}
    
    def get_repository(self, repo_class: type) -> BaseRepository:
    #    \"\"\"الحصول على مستودع\"\"\"
        if repo_class not in self._repositories:
            self._repositories[repo_class] = repo_class(self.session)
        return self._repositories[repo_class]
    
    def commit(self):
      #  \"\"\"تأكيد التغييرات\"\"\"
        self.session.commit()
    
    def rollback(self):
      #  \"\"\"تراجع عن التغييرات\"\"\"
        self.session.rollback()
    
    def close(self):
      #  \"\"\"إغلاق الجلسة\"\"\"
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()
