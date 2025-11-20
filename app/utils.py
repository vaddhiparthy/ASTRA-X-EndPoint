"""
Utility functions for ASTRA‑X‑Aggregator.

This module contains helpers to construct the prompt for the Ollama model,
to parse incoming webhook payloads and to decompress data where needed.
"""

import datetime
import json
import os
import zlib
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import crud
from .models import Message
from ..config.settings import get_static_prompt, get_structure_prompt, settings


def build_llm_messages(
    db: Session,
    *,
    current_text: str,
    current_role: str = "user",
    short_window_minutes: int = 15,
    summary_limit: int = 30,
) -> List[Dict[str, str]]:
    """Assemble a list of messages for the Ollama /api/chat call.

    The prompt is built from three parts:

    1. A system prompt specified via the `SYSTEM_PROMPT` environment variable.
    2. The most recent summaries (up to `summary_limit`) from the medium‑term
       store.  Each summary is added as a system message.
    3. Messages from the short‑term log within the last `short_window_minutes`
       minutes.  Events and system messages are treated as system messages,
       user messages retain their role, and assistant messages retain
       their role.

    Finally the current input is appended with the supplied role.

    Parameters
    ----------
    db : sqlalchemy.orm.Session
        Active database session.
    current_text : str
        The message text to append at the end of the prompt.
    current_role : str, optional
        The role of the current message ("user" or "system"), by default
        "user".
    short_window_minutes : int, optional
        Time window in minutes for retrieving short‑term context, by default 15.
    summary_limit : int, optional
        Number of summaries to include from the medium‑term store, by default 30.

    Returns
    -------
    list of dict
        A list of message objects suitable for the Ollama chat API.
    """
    messages: List[Dict[str, str]] = []

    # Add static and structure prompt instructions.  Each prompt is
    # inserted as a separate system message.  The order here
    # corresponds to the desired precedence: static (identity and
    # behaviour) first, then structure (format guidelines), then any
    # runtime override defined via environment variables.
    static_prompt = get_static_prompt()
    if static_prompt:
        messages.append({"role": "system", "content": static_prompt})
    structure_prompt = get_structure_prompt()
    if structure_prompt:
        messages.append({"role": "system", "content": structure_prompt})
    # If a system prompt override is defined (e.g. via SYSTEM_PROMPT),
    # append it as well.  This makes it easy to override behaviour on
    # the fly without editing files.
    if settings.system_prompt_override:
        messages.append({"role": "system", "content": settings.system_prompt_override})

    # Medium‑term summaries
    summaries = crud.get_recent_summaries(db, summary_limit)
    for summary in summaries:
        messages.append({"role": "system", "content": summary.summary_text})

    # Short‑term messages within the time window
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=short_window_minutes)
    short_msgs = crud.get_recent_messages(db, cutoff)
    for m in short_msgs:
        role = m.role.lower()
        if role not in {"user", "assistant"}:
            # treat events, system and unknown roles as system messages
            role = "system"
        messages.append({"role": role, "content": m.text})

    # Append current input message
    messages.append({"role": current_role, "content": current_text})
    return messages


def format_uptime_payload(payload: Dict[str, Any]) -> str:
    """Convert an Uptime Kuma webhook payload into a human readable string."""
    name = payload.get("monitor_name") or payload.get("name") or "Unknown monitor"
    status = payload.get("status") or payload.get("event") or "unknown"
    message = payload.get("msg") or payload.get("message")
    url = payload.get("monitor_url") or payload.get("url")
    parts = [f"[Uptime Kuma] {name} is {str(status).upper()}"]
    if url:
        parts.append(f"URL: {url}")
    if message:
        parts.append(f"Message: {message}")
    return " | ".join(parts)


def format_generic_payload(payload: Dict[str, Any]) -> str:
    """Convert an arbitrary JSON payload into indented JSON for the model."""
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        return str(payload)


def decompress_data(data: bytes) -> bytes:
    """Attempt to decompress compressed data.

    If the input bytes are not compressed (or decompression fails), the
    original bytes are returned unchanged.  This helper can be used
    before JSON parsing when processing webhook bodies.
    """
    try:
        return zlib.decompress(data)
    except Exception:
        return data