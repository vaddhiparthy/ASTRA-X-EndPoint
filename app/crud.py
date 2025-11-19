"""
High‑level CRUD operations for ASTRA‑X‑Aggregator.

These functions encapsulate database queries and updates.  They are
written to keep the FastAPI routes clean and to centralise query
optimisation.  All functions expect a SQLAlchemy session and commit is
handled by the dependency in `database.get_db()`.
"""

import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .models import Message, Summary


def create_message(
    db: Session,
    *,
    role: str,
    source: str,
    channel: str,
    text: str,
    raw_payload: Optional[dict] = None,
    meta: Optional[dict] = None,
) -> Message:
    """Create and persist a message record."""
    msg = Message(
        role=role,
        source=source,
        channel=channel,
        text=text,
        raw_payload=raw_payload,
        meta=meta,
    )
    db.add(msg)
    # Commit occurs in get_db() dependency
    return msg


def get_recent_messages(db: Session, since: datetime.datetime) -> List[Message]:
    """Return messages with ts greater than the given datetime, ordered ascending."""
    stmt = select(Message).where(Message.ts > since).order_by(Message.ts.asc())
    return list(db.scalars(stmt))


def get_messages_between(
    db: Session, start: datetime.datetime, end: datetime.datetime
) -> List[Message]:
    """Return messages between two timestamps inclusive."""
    stmt = (
        select(Message)
        .where(Message.ts >= start)
        .where(Message.ts <= end)
        .order_by(Message.ts.asc())
    )
    return list(db.scalars(stmt))


def get_last_n_messages(db: Session, limit: int) -> List[Message]:
    """Return the last `limit` messages sorted ascending."""
    if limit <= 0:
        return []
    # Subquery to find the cutoff timestamp
    subq = (
        select(Message.ts)
        .order_by(Message.ts.desc())
        .limit(limit)
        .subquery()
    )
    stmt = select(Message).where(Message.ts.in_(subq.c.ts)).order_by(Message.ts.asc())
    return list(db.scalars(stmt))


def get_recent_summaries(db: Session, limit: int) -> List[Summary]:
    """Return up to `limit` most recent summaries ordered ascending by time."""
    if limit <= 0:
        return []
    stmt = select(Summary).order_by(Summary.ts.desc()).limit(limit)
    # reversed to ascending order in memory
    return list(reversed(list(db.scalars(stmt))))