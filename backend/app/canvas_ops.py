"""Applying a single CanvasOp to an element list.

Mirrors `frontend/src/canvas/document.ts::applyOp` exactly: last-write-wins
upserts (ties broken by element id), deletes prune attached connectors too,
and clear wipes everything.
"""

from .models import CanvasElement, CanvasOp


def apply_op(elements: list[CanvasElement], op: CanvasOp) -> list[CanvasElement]:
    if op.type == "clear":
        return []

    if op.type == "delete":
        return [
            el
            for el in elements
            if el.id != op.id
            and not (el.kind == "connector" and (el.fromId == op.id or el.toId == op.id))
        ]

    if op.type == "upsert":
        incoming = op.element
        index = next((i for i, el in enumerate(elements) if el.id == incoming.id), None)
        if index is None:
            return [*elements, incoming]
        existing = elements[index]
        incoming_wins = incoming.updatedAt > existing.updatedAt or (
            incoming.updatedAt == existing.updatedAt and incoming.id >= existing.id
        )
        if not incoming_wins:
            return elements
        next_elements = list(elements)
        next_elements[index] = incoming
        return next_elements

    return elements
