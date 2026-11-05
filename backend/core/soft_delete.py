"""Soft-delete contract: shared recycle bin keyed to User UUID.

The owning business module keeps its own deleted_at/deleted_by/reason columns
and calls these helpers to mirror the row into the shared Core recycle bin.
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _uid(value) -> str:
    if value is None:
        raise ValueError("deleted_by / restored_by is required")
    if hasattr(value, "hex"):
        return value.hex
    return str(value)


async def soft_delete(session: AsyncSession, entity_type: str, entity_id,
                      deleted_by, reason: Optional[str] = None,
                      metadata: Optional[dict] = None) -> str:
    bin_id = uuid.uuid4().hex
    await session.execute(text(
        """INSERT INTO recycle_bin (id, entity_type, entity_id, deleted_by, reason, metadata)
           VALUES (:id, :entity_type, :entity_id, :deleted_by, :reason, :metadata)"""),
        {"id": bin_id, "entity_type": entity_type, "entity_id": str(entity_id),
         "deleted_by": _uid(deleted_by), "reason": reason,
         "metadata": json.dumps(metadata) if metadata is not None else None})
    return bin_id


async def restore(session: AsyncSession, entity_type: str, entity_id, restored_by) -> bool:
    r = await session.execute(text(
        """UPDATE recycle_bin SET restored_at = :at, restored_by = :by
           WHERE entity_type = :entity_type AND entity_id = :entity_id
             AND restored_at IS NULL"""),
        {"at": datetime.utcnow().isoformat(), "by": _uid(restored_by),
         "entity_type": entity_type, "entity_id": str(entity_id)})
    return r.rowcount > 0


async def restore_by_bin(session: AsyncSession, bin_id: str, restored_by) -> bool:
    r = await session.execute(text(
        """UPDATE recycle_bin SET restored_at = :at, restored_by = :by
           WHERE id = :id AND restored_at IS NULL"""),
        {"at": datetime.utcnow().isoformat(), "by": _uid(restored_by), "id": bin_id})
    return r.rowcount > 0


async def is_soft_deleted(session: AsyncSession, entity_type: str, entity_id) -> bool:
    r = await session.scalar(text(
        "SELECT 1 FROM recycle_bin WHERE entity_type = :t AND entity_id = :id AND restored_at IS NULL"),
        {"t": entity_type, "id": str(entity_id)})
    return r is not None


async def list_deleted(session: AsyncSession, entity_type: Optional[str] = None,
                       skip: int = 0, limit: int = 100):
    if entity_type:
        q = text("""SELECT id, entity_type, entity_id, deleted_by, deleted_at, reason, metadata
                    FROM recycle_bin WHERE restored_at IS NULL AND entity_type = :t
                    ORDER BY deleted_at DESC LIMIT :l OFFSET :s""")
        params = {"t": entity_type, "l": limit, "s": skip}
    else:
        q = text("""SELECT id, entity_type, entity_id, deleted_by, deleted_at, reason, metadata
                    FROM recycle_bin WHERE restored_at IS NULL
                    ORDER BY deleted_at DESC LIMIT :l OFFSET :s""")
        params = {"l": limit, "s": skip}
    rows = (await session.execute(q, params)).mappings()
    items = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (TypeError, ValueError):
                pass
        items.append(d)
    return items


async def purge(session: AsyncSession, bin_id: str) -> bool:
    r = await session.execute(text("DELETE FROM recycle_bin WHERE id = :id"), {"id": bin_id})
    return r.rowcount > 0
