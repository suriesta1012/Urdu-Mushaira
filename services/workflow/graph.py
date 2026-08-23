import logging
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
from infra.config import get_settings
from infra.postgres import PostgresCheckpointer

logger = logging.getLogger(__name__)

# Lazy-load postgres checkpointer
_postgres_checkpointer = None


def get_postgres_checkpointer():
    """Get or initialize PostgreSQL checkpointer."""
    global _postgres_checkpointer
    
    settings = get_settings()
    if not settings.postgres.enabled:
        logger.info("PostgreSQL checkpointer disabled")
        return None
    
    if _postgres_checkpointer is None:
        try:
            _postgres_checkpointer = PostgresCheckpointer(
                connection_string=settings.postgres.connection_string,
                table_name="langgraph_checkpoints"
            )
            logger.info(f"PostgreSQL checkpointer initialized: {settings.postgres.host}:{settings.postgres.port}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
            return None
    
    return _postgres_checkpointer


def build_graph():
    """
    Build the Urdu Mushaira workflow graph.
    
    Optionally uses PostgreSQL checkpointer for multi-session persistence
    if Postgres is enabled in config.
    """
    # Try to use PostgreSQL checkpointer if available
    checkpointer = get_postgres_checkpointer()
    
    # Fallback to in-memory checkpointer if Postgres unavailable
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        logger.warning("Using in-memory checkpointer (session state will be lost on restart)")
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


# Build graph once at module load
mushaira_graph = build_graph()
