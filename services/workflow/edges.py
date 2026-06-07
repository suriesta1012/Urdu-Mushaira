def should_continue(state: MushairaState) -> str:
    if state["current_position"] > 7:
        return "end"
    if state.get("status") == "failed":
        return "end"
    return "continue"
