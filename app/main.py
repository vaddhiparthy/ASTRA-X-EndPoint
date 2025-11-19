"""
Main FastAPI application for ASTRA‑X‑Aggregator.

This module defines all HTTP routes and glues together the database,
utility functions and the Ollama API.  It exposes endpoints for user
chat, webhook ingestion, history retrieval, log browsing and health
checks.  Messages are persisted in SQLite and context is assembled
dynamically on each request.
"""

import datetime
import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from sqlalchemy.orm import Session

from . import crud
from .database import get_db, init_db
from .models import Message
from .utils import (
    build_llm_messages,
    format_generic_payload,
    format_uptime_payload,
)


# ---------------------------------------------------------------------------
# Configuration via environment variables
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "hola")

# Create and configure the FastAPI application
app = FastAPI(title="ASTRA‑X‑Aggregator")

# Create DB tables on startup
@app.on_event("startup")
def on_startup() -> None:
    init_db()


# Mount static assets (JS/CSS) relative to this file
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root_index() -> HTMLResponse:
    """Serve the main HTML page."""
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Return a simple JSON object indicating service health.

    This endpoint does not call the Ollama API.  It can be extended to
    check connectivity by pinging `OLLAMA_HOST` if desired.
    """
    return {"status": "ok"}


async def call_ollama(messages: List[Dict[str, str]]) -> str:
    """Invoke the Ollama chat API and return the assistant reply.

    This helper constructs the payload, sends it to the configured
    Ollama host and handles errors consistently.
    """
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Ollama API error: {exc}")
    data = resp.json()
    reply = data.get("message", {}).get("content")
    if reply is None:
        raise HTTPException(status_code=500, detail="Ollama API returned no content")
    return reply


@app.post("/chat")
async def chat_endpoint(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Receive a chat message from the user and return the assistant’s reply."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    text = body.get("text") or body.get("message")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="'text' field is required")

    # Record the user message
    crud.create_message(
        db,
        role="user",
        source="web-chat",
        channel="chat",
        text=text,
    )

    # Build context and call the model
    messages = build_llm_messages(db, current_text=text, current_role="user")
    assistant_reply = await call_ollama(messages)

    # Record the assistant reply
    crud.create_message(
        db,
        role="assistant",
        source="ollama",
        channel="chat",
        text=assistant_reply,
    )

    return JSONResponse({"reply": assistant_reply})


@app.post("/webhook/uptime-kuma")
async def uptime_kuma_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Handle Uptime Kuma webhook payloads.

    The payload is normalised into a human readable message, stored as an
    event and then passed through the same model pipeline as chat messages.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    text = format_uptime_payload(payload)

    # Store the event message
    crud.create_message(
        db,
        role="event",
        source="uptime-kuma",
        channel="monitoring",
        text=text,
        raw_payload=payload,
    )

    # Build context and call the model (role=system for events)
    messages = build_llm_messages(db, current_text=text, current_role="system")
    assistant_reply = await call_ollama(messages)

    # Store assistant reply
    crud.create_message(
        db,
        role="assistant",
        source="ollama",
        channel="monitoring",
        text=assistant_reply,
    )

    return {"ok": "true"}


@app.post("/webhook/generic")
async def generic_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Accept arbitrary JSON payloads and summarise them.

    The raw payload is converted to text, stored as an event and used to
    construct a prompt.  An assistant reply is generated and recorded
    similarly to other pipelines.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    text = format_generic_payload(payload)
    crud.create_message(
        db,
        role="event",
        source="generic-webhook",
        channel="generic",
        text=text,
        raw_payload=payload,
    )

    messages = build_llm_messages(db, current_text=text, current_role="system")
    assistant_reply = await call_ollama(messages)
    crud.create_message(
        db,
        role="assistant",
        source="ollama",
        channel="generic",
        text=assistant_reply,
    )
    return {"ok": "true"}


@app.get("/history")
def history(
    after: Optional[str] = Query(default=None, description="ISO timestamp string"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return messages newer than the given timestamp.

    If no timestamp is provided, the last 50 messages are returned.  The
    response is ordered ascending by time.
    """
    if after:
        try:
            since_ts = datetime.datetime.fromisoformat(after)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid 'after' timestamp")
        msgs = crud.get_recent_messages(db, since_ts)
    else:
        msgs = crud.get_last_n_messages(db, limit=50)
    return [m.to_dict() for m in msgs]


@app.get("/data")
def data_browser(
    start: str = Query(..., description="ISO 8601 start time"),
    end: str = Query(..., description="ISO 8601 end time"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return messages between the start and end timestamps inclusive."""
    try:
        start_ts = datetime.datetime.fromisoformat(start)
        end_ts = datetime.datetime.fromisoformat(end)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start/end timestamps")
    if end_ts < start_ts:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")
    msgs = crud.get_messages_between(db, start_ts, end_ts)
    return [m.to_dict() for m in msgs]