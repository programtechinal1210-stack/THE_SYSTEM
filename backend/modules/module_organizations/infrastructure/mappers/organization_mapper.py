from infrastructure.database.models.organization_model import OrganizationModel
from ...domain.entities.organization import Organization

class OrganizationMapper:
    @staticmethod
    def to_entity(model: OrganizationModel) -> Organization:
        return Organization(id=model.id, name=model.name, parent_id=model.parent_id, is_active=model.is_active)
