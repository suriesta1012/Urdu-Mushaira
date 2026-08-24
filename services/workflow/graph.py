import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
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
from infra.config import get_settings
from infra.postgres import get_postgres_checkpointer

logger = logging.getLogger(__name__)

# Lazy-load postgres checkpointer
_postgres_checkpointer = None


def get_or_init_checkpointer():
    """
    Get or initialize PostgreSQL checkpointer.
    
    Returns the official LangGraph PostgresSaver if enabled and available,
    otherwise falls back to in-memory MemorySaver.
    """
    global _postgres_checkpointer
    
    settings = get_settings()
    if not settings.postgres.enabled:
        logger.info("PostgreSQL checkpointer disabled, using in-memory checkpointer")
        return MemorySaver()
    
    if _postgres_checkpointer is None:
        _postgres_checkpointer = get_postgres_checkpointer()
    
    # Fallback to in-memory checkpointer if Postgres unavailable
    if _postgres_checkpointer is None:
        logger.warning("Using in-memory checkpointer (session state will be lost on restart)")
        return MemorySaver()
    
    return _postgres_checkpointer


def build_graph():
    """
    Build the Urdu Mushaira workflow graph.
    
    Optionally uses PostgreSQL checkpointer for multi-session persistence
    if Postgres is enabled in config.
    
    The graph supports both sync (graph.invoke) and async (graph.ainvoke) execution:
    - graph.invoke() works with the sync PostgresSaver.get/put methods
    - graph.ainvoke() works with the async PostgresSaver.get_async/put_async methods
    - When running graph.invoke() in a thread executor, the sync methods are used
    """
    # Try to use PostgreSQL checkpointer if available
    checkpointer = get_or_init_checkpointer()
    
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


# Build graph once at module load
mushaira_graph = build_graph()
