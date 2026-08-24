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
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.workflow.graph import build_graph
from services.workflow.state import MushairaState, WorkflowStatus
from infra.langfuse import trace_mushaira_session

app = FastAPI(title="Urdu Mushaira API")

# In-memory session store (replace with Redis / DB in production)
_sessions: Dict[str, Dict[str, Any]] = {}


# ------------------------------------------------------------------ #
# Request / response models                                          #
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
# Helpers                                                            #
# ------------------------------------------------------------------ #

def _initial_state(session_id: str, theme: str) -> MushairaState:
    """
    Initial graph state. Use WorkflowStatus enum values for the graph runtime.
    Node-specific fields used by the workflow are included here so nodes can
    read/write them without KeyError.
    
    The session_id is passed to the graph and used as thread_id for checkpoint
    persistence (via the configurable dict when calling graph.invoke).
    """
    return {
        "session_id": session_id,
        "theme": theme,
        "current_position": 1,
        "verses": [],
        "status": WorkflowStatus.RUNNING,
        "error": None,
        "failed_poets": [],
        "poet_conversations": {},
        "poet_errors": {},
        "skipped_poets": [],
        "failed_poets_positions": [],
        "current_poet_retry_count": 0,
        # Node-specific fields
        "draft_verse": None,
        "pending_poet_key": None,
        "validation_passed": False,
        "validation_error": None,
    }


def _status_to_str(status_value) -> str:
    """Convert WorkflowStatus enum or string-like status to plain string for HTTP responses."""
    try:
        return status_value.value  # enum
    except Exception:
        return str(status_value)


# ------------------------------------------------------------------ #
# Route 1 — Server-Sent Events streaming                             #
# Each verse is emitted the moment it is composed.                   #
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
        # Initialize graph state for this session
        state = _initial_state(session_id, req.theme)
        try:
            # astream yields {"node_name": updated_state_slice} after each node
            # Verses are only committed (made visible) in the accept_verse node;
            # stream from accept_verse so clients receive complete verses.
            # Pass config with thread_id = session_id for checkpoint retrieval
            config = {"configurable": {"thread_id": session_id}}
            async for chunk in graph.astream(state, config=config):
                # When accept_verse runs it emits the updated verses list
                if "accept_verse" in chunk:
                    node_out = chunk["accept_verse"]
                    verses = node_out.get("verses", [])
                    if verses:
                        latest = verses[-1]
                        payload = json.dumps({"event": "verse", "data": latest})
                        yield f"data: {payload}\n\n"
                        # yield control so the event loop can schedule other tasks
                        await asyncio.sleep(0)

                elif "skip_poet" in chunk:
                    node_out = chunk["skip_poet"]
                    skipped = node_out.get("skipped_poets", [])
                    if skipped:
                        payload = json.dumps({
                            "event": "skip",
                            "poet": skipped[-1],
                        })
                        yield f"data: {payload}\n\n"

            # Graph finished successfully
            try:
                trace.update(output={"session_id": session_id})
            except Exception:
                # tracing is best-effort
                pass

            yield f"data: {json.dumps({'event': 'done', 'status': 'completed'})}\n\n"

        except Exception as e:
            # Capture error in trace and stream an error event to client
            try:
                trace.update(level="ERROR", status_message=str(e))
            except Exception:
                pass
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
# Route 2 — Background task + polling                                #
# ------------------------------------------------------------------ #

@app.post("/mushaira", response_model=MushairaStartResponse)
async def start_mushaira(req: MushairaRequest):
    """
    Kick off a mushaira session in the background.
    Returns a session_id immediately; poll /mushaira/{session_id} for results.
    """
    session_id = str(uuid.uuid4())
    # Store user-facing session state as plain serializable values (strings for status)
    _sessions[session_id] = {
        "session_id": session_id,
        "theme": req.theme,
        "verses": [],
        "status": WorkflowStatus.RUNNING.value,
        "failed_poets": [],
        "error": None,
    }
    asyncio.create_task(_run_mushaira_background(session_id, req.theme))
    return MushairaStartResponse(
        session_id=session_id,
        theme=req.theme,
        status=WorkflowStatus.RUNNING.value,
    )


@app.get("/mushaira/{session_id}", response_model=MushairaStatusResponse)
async def get_mushaira_status(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _sessions[session_id]
    return MushairaStatusResponse(**s)


async def _run_mushaira_background(session_id: str, theme: str):
    """
    Run the long-lived graph.invoke(...) in a thread executor so it doesn't block the event loop.
    Update the in-memory session store with results (convert enum statuses to strings).
    
    The session_id is passed as thread_id in the graph config for checkpoint persistence.
    This allows LangGraph's PostgresSaver to:
    1. Save checkpoints associated with this thread_id
    2. Retrieve previous checkpoints if resuming a workflow
    3. Maintain session-specific state across restarts
    """
    trace = trace_mushaira_session(session_id, theme)
    graph = build_graph()
    state = _initial_state(session_id, theme)
    try:
        # Run in a thread so the blocking LangGraph .invoke() doesn't stall
        # the asyncio event loop. The PostgresSaver's sync methods (get/put)
        # are used during invoke() execution.
        loop = asyncio.get_event_loop()
        config = {"configurable": {"thread_id": session_id}}
        final_state = await loop.run_in_executor(
            None, lambda: graph.invoke(state, config=config)
        )

        # Normalize status and update the user-facing session store
        status_val = final_state.get("status", WorkflowStatus.COMPLETED)
        _sessions[session_id].update({
            "verses": final_state.get("verses", []),
            "status": _status_to_str(status_val),
            "failed_poets": final_state.get("failed_poets", []),
            "error": final_state.get("error"),
        })

        try:
            trace.update(output={"verse_count": len(final_state.get("verses", []))})
        except Exception:
            pass

    except Exception as e:
        # Record failure for pollers
        _sessions[session_id].update({"status": WorkflowStatus.FAILED.value, "error": str(e)})
        try:
            trace.update(level="ERROR", status_message=str(e))
        except Exception:
            pass


# ------------------------------------------------------------------ #
# Health                                                             #
# ------------------------------------------------------------------ #

@app.get("/health")
def health():
    return {"status": "ok"}
