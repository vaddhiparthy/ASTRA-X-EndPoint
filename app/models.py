"""
ORM models for ASTRA‑X‑Aggregator.

This module defines two tables:

* **Message** – stores every incoming and outgoing chat event.  Fields
  include a timestamp, role (user/assistant/event/system), source
  (e.g. web‑chat, uptime‑kuma), channel (chat, monitoring, etc.),
  the plain text content, and optional raw payload and metadata as JSON.
* **Summary** – holds summarised chunks of conversation for the medium‑
  term context window.  Summaries are not created by the pipeline yet
  but the table is available for future jobs.
"""

import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import declarative_base

from .database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    role = Column(String(20), nullable=False)
    source = Column(String(50), nullable=False)
    channel = Column(String(50), nullable=False)
    text = Column(Text, nullable=False)
    raw_payload = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        """Return a JSON serialisable representation of this message."""
        return {
            "id": self.id,
            "ts": self.ts.isoformat(),
            "role": self.role,
            "source": self.source,
            "channel": self.channel,
            "text": self.text,
            "raw_payload": self.raw_payload,
            "meta": self.meta,
        }


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    summary_text = Column(Text, nullable=False)
    source_range = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts.isoformat(),
            "summary_text": self.summary_text,
            "source_range": self.source_range,
            "tags": self.tags,
        }