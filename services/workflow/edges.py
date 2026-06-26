
from services.workflow.state import MushairaState, WorkflowStatus
from agents.poet_config import RECITATION_ORDER

MAX_SKIP = 2   # abort the whole mushaira if more than this many poets fail

MAX_POET_ATTEMPTS=3

def _can_try_current_poet_again(state: MushairaState) -> bool:
    
      return state.get("current_poet_retry_count", 0) < MAX_POET_ATTEMPTS


def route_after_poet_turn(state: MushairaState) -> str:
    if state.get("status") == WorkflowStatus.FAILED:
        return "end"

    if state.get("error"):
        if _can_try_current_poet_again(state):
            return "retry"
        return "skip"

    return "validate"
    

def route_after_validation(state: MushairaState) -> str:
    if state.get("status") == WorkflowStatus.FAILED:
        return "end"

    if state.get("validation_passed"):
        return "accept"

    if _can_try_current_poet_again(state):
        return "retry"

    return "skip"


def route_after_position_advance(state: MushairaState) -> str:
    if state.get("status") == WorkflowStatus.FAILED:
        return "end"

    # All poets have recited
    if state["current_position"] > len(RECITATION_ORDER):
        return "end"

    if len(state.get("failed_poets", [])) >= MAX_SKIP:
        return "end"

    return "continue" 
