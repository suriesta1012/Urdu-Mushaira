
from services.workflow.state import MushairaState
from langgraph.checkpoint.memory import MemorySaver
MAX_SKIP = 2   # abort the whole mushaira if more than this many poets fail


def should_continue(state: MushairaState) -> str:
    # All 7 positions completed successfully
    if state.status == WorkflowStatus.FAILED:
        return "end"
    
    # All poets have recited
    if state.current_position > 7:
        return "end"
    
    # A poet just failed
    if state.failed_poets and state.current_position in state.failed_poets_positions:
        # (you'd track which position each failed poet was at)
        failed_count = len(state.failed_poets)
        if failed_count >= MAX_SKIP:
            return "end"  # Too many failures
        return "skip"  # Skip this poet, continue
    
    return "continue"
