from ..models.entity_type_model import EntityTypeModel
from ...domain.entities.entity_type import EntityType

class EntityTypeMapper:
    @staticmethod
    def to_entity(model: EntityTypeModel) -> EntityType:
        return EntityType(id=model.id, code=model.code, name=model.name, description=model.description, is_active=model.is_active, created_at=model.created_at, updated_at=model.updated_at)
