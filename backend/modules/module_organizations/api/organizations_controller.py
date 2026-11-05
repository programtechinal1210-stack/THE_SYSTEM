from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import shutil
import os

from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User

from ..domain.entities.entity_type import EntityType
from ..domain.entities.entity import Entity
from ..infrastructure.models.entity_type_model import EntityTypeModel
from ..infrastructure.models.entity_model import EntityModel
from ..infrastructure.mappers.entity_type_mapper import EntityTypeMapper
from ..infrastructure.mappers.entity_mapper import EntityMapper

from pydantic import BaseModel, Field

from ..application.entity_dtos import EntityTypeDTO, CreateEntityDTO, UpdateEntityDTO, EntityResponseDTO

router = APIRouter(tags=["organizations"])

from ..infrastructure.repositories.entity_repository import BaseRepo

def get_entity_repo(s: AsyncSession = Depends(get_session, scope="function")): return BaseRepo(s, EntityModel, EntityMapper)
def get_type_repo(s: AsyncSession = Depends(get_session, scope="function")): return BaseRepo(s, EntityTypeModel, EntityTypeMapper)

# ═══════════ ENTITY TYPES ═══════════
@router.get("/entity-types", response_model=List[EntityTypeDTO])
async def list_types(repo = Depends(get_type_repo)):
    return [EntityTypeDTO.model_validate(e) for e in await repo.all()]

@router.post("/entity-types", response_model=EntityTypeDTO, status_code=201)
async def create_type(data: EntityTypeDTO, u: User = Depends(get_current_user), repo = Depends(get_type_repo)):
    return EntityTypeDTO.model_validate(await repo.save(EntityType(**data.model_dump(exclude={"id"}))))

@router.get("/entity-types/{id}", response_model=EntityTypeDTO)
async def get_type(id: UUID, repo = Depends(get_type_repo)):
    e = await repo.get(id)
    if not e: raise HTTPException(404, "Entity type not found")
    return EntityTypeDTO.model_validate(e)

@router.put("/entity-types/{id}", response_model=EntityTypeDTO)
async def update_type(id: UUID, data: EntityTypeDTO, repo = Depends(get_type_repo)):
    e = await repo.get(id)
    if not e: raise HTTPException(404, "Entity type not found")
    return EntityTypeDTO.model_validate(await repo.save(e.model_copy(update=data.model_dump(exclude_unset=True, exclude={"id"}))))

@router.delete("/entity-types/{id}", status_code=204)
async def delete_type(id: UUID, repo = Depends(get_type_repo)):
    if not await repo.delete(id): raise HTTPException(404)

# ═══════════ ENTITIES ═══════════
@router.get("", response_model=List[EntityResponseDTO])
async def list_entities(repo = Depends(get_entity_repo)):
    return [EntityResponseDTO.model_validate(e) for e in await repo.all()]

@router.get("/{id}", response_model=EntityResponseDTO)
async def get_entity(id: UUID, repo = Depends(get_entity_repo)):
    e = await repo.get(id)
    if not e: raise HTTPException(404, "Entity not found")
    return EntityResponseDTO.model_validate(e)

@router.post("", response_model=EntityResponseDTO, status_code=201)
async def create_entity(data: CreateEntityDTO, u: User = Depends(get_current_user), repo = Depends(get_entity_repo)):
    await validate_entity_parent(repo, data.parent_id)
    return EntityResponseDTO.model_validate(await repo.save(Entity(**data.model_dump())))

@router.put("/{id}", response_model=EntityResponseDTO)
async def update_entity(id: UUID, data: UpdateEntityDTO, repo = Depends(get_entity_repo)):
    e = await repo.get(id)
    if not e: raise HTTPException(404, "غير موجود")
    
    old_parent = str(e.parent_id or "")
    new_parent = str(data.parent_id or "")
    
    if "parent_id" in data.model_fields_set:
        await validate_entity_parent(repo, data.parent_id, id)
    updated = await repo.save(e.model_copy(update=data.model_dump(exclude_unset=True)))
    
    if data.parent_id is not None and new_parent != old_parent:
        print(f"[MOVE] Entity {id} parent changed: {old_parent} -> {new_parent}")
    
    return EntityResponseDTO.model_validate(updated)

@router.delete("/{id}", status_code=204)
async def delete_entity(id: UUID, repo = Depends(get_entity_repo)):
    if not await repo.delete(id): raise HTTPException(404)

async def validate_entity_parent(repo, parent_id, entity_id=None):
    if parent_id is None:
        return
    seen = {entity_id} if entity_id else set()
    while parent_id:
        if parent_id in seen:
            raise HTTPException(409, "Entity hierarchy cycle")
        seen.add(parent_id)
        parent = await repo.get(parent_id)
        if not parent:
            raise HTTPException(422, "Parent entity not found")
        if not parent.is_active:
            raise HTTPException(422, "Parent entity must be active")
        parent_id = parent.parent_id
