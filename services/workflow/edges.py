
from services.workflow.state import MushairaState

MAX_SKIP = 2   # abort the whole mushaira if more than this many poets fail


def should_continue(state: MushairaState) -> str:
    # All 7 positions completed successfully
    if state["current_position"] > 7:
        return "end"

    # A poet just failed
    if state.get("status") == "failed":
        failed = state.get("failed_poets", [])
        if len(failed) >= MAX_SKIP:
            # Too many failures — abort rather than produce a hollow mushaira
            return "end"
        # Skip this poet and continue with the next
        return "skip"

    return "continue"
