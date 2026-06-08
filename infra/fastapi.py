"""
FastAPI entry-point for the Urdu Mushaira service.

Two ways to consume:

1. POST /mushaira/stream?theme=...
   Server-Sent Events — each verse is pushed as it is composed.
   The client never waits 35 seconds for a batch response.

2. POST /mushaira          → returns session_id immediately
   GET  /mushaira/{id}     → polls current state (verses so far + status)
   This is the background-task / polling variant.
"""

import asyncio
import json
import uuid
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.workflow.graph import build_graph
from services.workflow.state import MushairaState
from infra.langfuse import trace_mushaira_session

app = FastAPI(title="Urdu Mushaira API")

# In-memory session store (replace with Redis / DB in production)
_sessions: Dict[str, dict] = {}


# ------------------------------------------------------------------ #
# Request / response models                                            #
# ------------------------------------------------------------------ #

class MushairaRequest(BaseModel):
    theme: str


class MushairaStartResponse(BaseModel):
    session_id: str
    theme: str
    status: str


class MushairaStatusResponse(BaseModel):
    session_id: str
    theme: str
    verses: list
    status: str
    failed_poets: list
    error: str | None


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _initial_state(session_id: str, theme: str) -> MushairaState:
    return {
        "session_id": session_id,
        "theme": theme,
        "current_position": 1,
        "verses": [],
        "status": "running",
        "error": None,
        "retry_count": 0,
        "failed_poets": [],
    }


# ------------------------------------------------------------------ #
# Route 1 — Server-Sent Events streaming                               #
# Each verse is emitted the moment it is composed.                    #
# ------------------------------------------------------------------ #

@app.post("/mushaira/stream")
async def stream_mushaira(req: MushairaRequest):
    """
    SSE endpoint. Connect with:
        curl -N -X POST "http://localhost:8000/mushaira/stream" \
             -H "Content-Type: application/json" \
             -d '{"theme": "ishq aur judai"}'

    Each event is a JSON-serialised PoetryData dict.
    A final {"event": "done", "status": "completed"} event signals the end.
    """
    session_id = str(uuid.uuid4())
    trace = trace_mushaira_session(session_id, req.theme)
    graph = build_graph()   # fresh graph per session so memory is isolated

    async def event_generator():
        state = _initial_state(session_id, req.theme)
        try:
            # astream yields {"node_name": updated_state_slice} after each node
            async for chunk in graph.astream(state):
                if "poet_turn" in chunk:
                    node_out = chunk["poet_turn"]
                    verses = node_out.get("verses", [])
                    if verses:
                        latest = verses[-1]
                        payload = json.dumps({"event": "verse", "data": latest})
                        yield f"data: {payload}\n\n"
                        await asyncio.sleep(0)   # yield control to event loop

                elif "skip_poet" in chunk:
                    node_out = chunk["skip_poet"]
                    failed = node_out.get("failed_poets", [])
                    if failed:
                        payload = json.dumps({
                            "event": "skip",
                            "poet": failed[-1],
                        })
                        yield f"data: {payload}\n\n"

            # Graph finished
            trace.update(output={"session_id": session_id})
            yield f"data: {json.dumps({'event': 'done', 'status': 'completed'})}\n\n"

        except Exception as e:
            trace.update(level="ERROR", status_message=str(e))
            yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ------------------------------------------------------------------ #
# Route 2 — Background task + polling                                  #
# ------------------------------------------------------------------ #

@app.post("/mushaira", response_model=MushairaStartResponse)
async def start_mushaira(req: MushairaRequest):
    """
    Kick off a mushaira session in the background.
    Returns a session_id immediately; poll /mushaira/{session_id} for results.
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "session_id": session_id,
        "theme": req.theme,
        "verses": [],
        "status": "running",
        "failed_poets": [],
        "error": None,
    }
    asyncio.create_task(_run_mushaira_background(session_id, req.theme))
    return MushairaStartResponse(
        session_id=session_id,
        theme=req.theme,
        status="running",
    )


@app.get("/mushaira/{session_id}", response_model=MushairaStatusResponse)
async def get_mushaira_status(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _sessions[session_id]
    return MushairaStatusResponse(**s)


async def _run_mushaira_background(session_id: str, theme: str):
    trace = trace_mushaira_session(session_id, theme)
    graph = build_graph()
    state = _initial_state(session_id, theme)
    try:
        # Run in a thread so the blocking LangGraph .invoke() doesn't stall
        # the asyncio event loop
        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(None, graph.invoke, state)
        _sessions[session_id].update({
            "verses": final_state.get("verses", []),
            "status": final_state.get("status", "completed"),
            "failed_poets": final_state.get("failed_poets", []),
            "error": final_state.get("error"),
        })
        trace.update(output={"verse_count": len(final_state.get("verses", []))})
    except Exception as e:
        _sessions[session_id].update({"status": "failed", "error": str(e)})
        trace.update(level="ERROR", status_message=str(e))


# ------------------------------------------------------------------ #
# Health                                                               #
# ------------------------------------------------------------------ #

@app.get("/health")
def health():
    return {"status": "ok"}

