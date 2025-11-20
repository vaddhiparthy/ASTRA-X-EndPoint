"""
Main FastAPI application for ASTRA-X-Aggregator.

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

from config.settings import settings

app = FastAPI(title="ASTRA-X-Aggregator")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root_index() -> HTMLResponse:
    index_path = os.path.join(static_dir, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    chat_name = os.getenv("CHATBOT_NAME", "ASTRA-X-Aggregator")
    content = content.replace("{{CHATBOT_NAME}}", chat_name)
    return HTMLResponse(content=content)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


# -------------------------------
#  FIXED OLLAMA IMPLEMENTATION
# -------------------------------
async def call_llm(messages: List[Dict[str, str]]) -> str:
    provider = settings.provider.lower()

    if provider == "ollama":
        base = settings.ollama_host.rstrip("/")
        url = f"{base}/api/generate"

        # Convert OpenAI-style messages -> one flat text prompt
        prompt_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in messages]
        )

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt_text,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Ollama API error: {exc}"
                )

        data = resp.json()
        reply = data.get("response")

        if reply is None:
            raise HTTPException(
                status_code=500,
                detail="Ollama returned no response"
            )

        return reply

    # -----------------
    # OPENAI BACKEND
    # -----------------
    if provider == "openai":
        api_key = settings.openai_api_key
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY missing"
            )

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": settings.openai_model,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"OpenAI error: {exc}"
                )

        data = resp.json()
        try:
            reply = data["choices"][0]["message"]["content"]
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="OpenAI returned invalid response"
            )

        return reply

    raise HTTPException(
        status_code=500,
        detail=f"Unsupported provider: {settings.provider}"
    )


@app.post("/chat")
async def chat_endpoint(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    text = body.get("text") or body.get("message")
    if not text:
        raise HTTPException(status_code=400, detail="'text' field is required")

    crud.create_message(
        db, role="user", source="web-chat", channel="chat", text=text
    )

    messages = build_llm_messages(db, current_text=text, current_role="user")
    assistant_reply = await call_llm(messages)

    crud.create_message(
        db, role="assistant", source="ollama", channel="chat", text=assistant_reply
    )

    return JSONResponse({"reply": assistant_reply})


@app.post("/webhook/uptime-kuma")
async def uptime_kuma_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    text = format_uptime_payload(payload)
    crud.create_message(
        db, role="event", source="uptime-kuma", channel="monitoring",
        text=text, raw_payload=payload
    )

    messages = build_llm_messages(db, current_text=text, current_role="system")
    assistant_reply = await call_llm(messages)

    crud.create_message(
        db, role="assistant", source="ollama", channel="monitoring",
        text=assistant_reply
    )

    return {"ok": "true"}


@app.post("/webhook/generic")
async def generic_webhook(request: Request, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    text = format_generic_payload(payload)

    crud.create_message(
        db, role="event", source="generic-webhook", channel="generic",
        text=text, raw_payload=payload
    )

    messages = build_llm_messages(db, current_text=text, current_role="system")
    assistant_reply = await call_llm(messages)

    crud.create_message(
        db, role="assistant", source="ollama", channel="generic",
        text=assistant_reply
    )

    return {"ok": "true"}


@app.get("/history")
def history(
    after: Optional[str] = Query(default=None, description="ISO timestamp string"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:

    # Fix: handle timestamps ending with 'Z' (JavaScript default)
    if after:
        clean = after.replace("Z", "")
        try:
            since_ts = datetime.datetime.fromisoformat(clean)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid 'after' timestamp")
        msgs = crud.get_recent_messages(db, since_ts)

    else:
        msgs = crud.get_last_n_messages(db, limit=50)

    return [m.to_dict() for m in msgs]

@app.get("/data")
def data_browser(
    start: str = Query(...), end: str = Query(...), db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:

    try:
        start_ts = datetime.datetime.fromisoformat(start)
        end_ts = datetime.datetime.fromisoformat(end)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamps")

    if end_ts < start_ts:
        raise HTTPException(status_code=400, detail="'end' must be after 'start'")

    msgs = crud.get_messages_between(db, start_ts, end_ts)
    return [m.to_dict() for m in msgs]
