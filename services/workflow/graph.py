from langgraph.graph import StateGraph, END
from services.workflow.state import MushairaState
from services.workflow.nodes import poet_turn_node, skip_poet_node, finalize_node
from services.workflow.edges import should_continue
from langgraph.checkpoint.memory import MemorySaver


def build_graph():
    checkpointer = MemorySaver()
    g = StateGraph(MushairaState)
    
    g.add_node("poet_turn", poet_turn_node)
    g.add_node("skip_poet", skip_poet_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("poet_turn")

    g.add_conditional_edges(
        "poet_turn",
        should_continue,
        {
            "continue": "poet_turn",
            "skip":     "skip_poet",
            "end":      "finalize",
        },
    )

    # After skipping a poet, loop back into the turn cycle
    g.add_edge("skip_poet", "poet_turn")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)


mushaira_graph = build_graph()
