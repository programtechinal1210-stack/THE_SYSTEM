from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Type, Optional, List, Any
from infrastructure.database.models.base_model import BaseModel

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
  #  \"\"\"مستودع أساسي - عمليات CRUD مشتركة\"\"\"
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, id: Any) -> Optional[T]:
      #  \"\"\"الحصول على سجل بواسطة المعرف\"\"\"
        return self.session.query(self.model_class).filter(
            self.model_class.id == id
        ).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
      #  \"\"\"الحصول على جميع السجلات\"\"\"
        return self.session.query(self.model_class).offset(skip).limit(limit).all()
    
    def create(self, **kwargs) -> T:
      #  \"\"\"إنشاء سجل جديد\"\"\"
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance
    
    def update(self, id: Any, **kwargs) -> Optional[T]:
       # \"\"\"تحديث سجل\"\"\"
        instance = self.get_by_id(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.session.flush()
        return instance
    
    def delete(self, id: Any, soft: bool = True) -> bool:
      #  \"\"\"حذف سجل\"\"\"
        instance = self.get_by_id(id)
        if not instance:
            return False
        if soft and hasattr(instance, 'is_active'):
            instance.is_active = False
        else:
            self.session.delete(instance)
        self.session.flush()
        return True
    
    def count(self) -> int:
       # \"\"\"عدد السجلات\"\"\"
        return self.session.query(self.model_class).count()
