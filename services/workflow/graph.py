from langgraph.graph import StateGraph, END
from services.workflow.state import MushairaState
from services.workflow.nodes import (
    accept_verse_node,
    finalize_node,
    poet_turn_node,
    skip_poet_node,
    validate_verse_node,
)
from services.workflow.edges import (
    route_after_poet_turn,
    route_after_position_advance,
    route_after_validation,
)
from langgraph.checkpoint.memory import MemorySaver


def build_graph():
    checkpointer = MemorySaver()
    g = StateGraph(MushairaState)
    
    g.add_node("poet_turn", poet_turn_node)
    g.add_node("validate_verse", validate_verse_node)
    g.add_node("accept_verse", accept_verse_node)
    g.add_node("skip_poet", skip_poet_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("poet_turn")

    g.add_conditional_edges(
        "poet_turn",
        route_after_poet_turn,
        {
            "validate": "validate_verse",
            "retry":    "poet_turn",
            "skip":     "skip_poet",
            "end":      "finalize",
        },
    )

    g.add_conditional_edges(
        "validate_verse",
        route_after_validation,
        {
            "accept": "accept_verse",
            "retry":  "poet_turn",
            "skip":   "skip_poet",
            "end":    "finalize",
        },
    )

    g.add_conditional_edges(
        "accept_verse",
        route_after_position_advance,
        {
            "continue": "poet_turn",
            "end":      "finalize",
        },
    )

    g.add_conditional_edges(
        "skip_poet",
        route_after_position_advance,
        {
            "continue": "poet_turn",
            "end":      "finalize",
        },
    )

    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)


mushaira_graph = build_graph()
