
from services.workflow.state import MushairaState, WorkflowStatus


MAX_SKIP = 2   # abort the whole mushaira if more than this many poets fail


def should_continue(state: MushairaState) -> str:
    # Check if workflow was explicitly failed
    if state.get("status") == WorkflowStatus.FAILED:
        return "end"
    
    # All poets have recited
    if state["current_position"] > len(RECITATION_ORDER):
        return "end"
    
    # A poet just failed (current_position is still at the failing poet)
    failed_poets_positions = state.get("failed_poets_positions", [])
    if state["current_position"] in failed_poets_positions:
        failed_count = len(state.get("failed_poets", []))
        if failed_count >= MAX_SKIP:
            return "end"  # Too many failures
        return "skip"  # Skip this poet, continue
    
    return "continue"
