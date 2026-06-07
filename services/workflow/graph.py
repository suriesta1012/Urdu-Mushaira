from langgraph.graph import StateGraph, END
from services.workflow.state import MushairaState
from services.workflow.nodes import poet_turn_node, finalize_node
from services.workflow.edges import should_continue

def build_graph():
    g = StateGraph(MushairaState)
    g.add_node("poet_turn", poet_turn_node)
    g.add_node("finalize", finalize_node)
    g.set_entry_point("poet_turn")
    g.add_conditional_edges(
        "poet_turn",
        should_continue,
        {"continue": "poet_turn", "end": "finalize"},
    )
    g.add_edge("finalize", END)
    return g.compile()

mushaira_graph = build_graph()
