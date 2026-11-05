"""Baseline + dependency contracts. Baselines are read-only immutable snapshots."""
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

DependencyType = Annotated[str, StringConstraints(
    pattern=r'^(finish_to_start|start_to_start|finish_to_finish|start_to_finish)$')]


class DependencyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    predecessor_id: UUID
    successor_id: UUID
    dependency_type: DependencyType = 'finish_to_start'
