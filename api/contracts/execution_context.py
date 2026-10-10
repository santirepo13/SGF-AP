"""Execution context contract."""

from __future__ import annotations

from dataclasses import dataclass

from .actor_context import ActorContext


ACTOR_REQUIRED_OPERATIONS: frozenset[str] = frozenset(
    {
        "register_ticket",
        "validate_ticket",
        "prioritize_ticket",
        "assign_ticket",
        "attend_ticket",
        "review_ticket_closure",
        "create_evidence",
        "create_history_event",
    }
)


@dataclass(frozen=True)
class ExecutionContext:
    operation: str
    correlation_id: str
    actor: ActorContext | None = None


def requires_actor(operation: str) -> bool:
    """Return whether the named application operation requires an actor."""

    return operation in ACTOR_REQUIRED_OPERATIONS


def validate_actor_context(context: ExecutionContext) -> ExecutionContext:
    """Validate the actor requirement without performing permission checks."""

    if requires_actor(context.operation) and context.actor is None:
        raise ValueError(f"operation {context.operation!r} requires an actor")
    return context
