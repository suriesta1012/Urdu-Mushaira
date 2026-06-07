from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from services.workflow.graph import mushaira_graph
from infra.langfuse import trace_mushaira_session
import uuid

app = FastAPI(title="Urdu Mushaira API")

class MushairaRequest(BaseModel):
    theme: str

class MushairaResponse(BaseModel):
    session_id: str
    theme: str
    verses: list
    status: str

@app.post("/mushaira", response_model=MushairaResponse)
async def run_mushaira(req: MushairaRequest):
    session_id = str(uuid.uuid4())
    trace = trace_mushaira_session(session_id, req.theme)

    initial_state = {
        "session_id": session_id,
        "theme": req.theme,
        "current_position": 1,
        "previous_sher": None,
        "verses": [],
        "status": "running",
        "error": None,
    }
    try:
        final_state = mushaira_graph.invoke(initial_state)
        trace.update(output={"verse_count": len(final_state["verses"])})
        return MushairaResponse(**final_state)
    except Exception as e:
        trace.update(level="ERROR", status_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
