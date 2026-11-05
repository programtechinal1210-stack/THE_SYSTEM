from ..models.entity_model import EntityModel
from ...domain.entities.entity import Entity

class EntityMapper:
    @staticmethod
    def to_entity(model: EntityModel) -> Entity:
        return Entity(id=model.id, name=model.name, code=model.code, entity_type_id=model.entity_type_id, contact_person=model.contact_person, phone=model.phone, email=model.email, address=model.address, parent_id=model.parent_id, is_active=model.is_active, created_at=model.created_at, updated_at=model.updated_at)
