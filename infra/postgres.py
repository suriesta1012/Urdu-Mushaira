"""
PostgreSQL Checkpointer for LangGraph.

Replaces custom implementation with the official LangGraph PostgreSQL checkpointer.
Enables multi-session learning by persisting graph state across sessions.
Stores checkpoints in Postgres, allowing recovery and state inspection.

Supports:
- Persisting graph state across sessions
- Multi-session learning (retrieve prior poet behaviors, themes)
- Session recovery on failure
- Checkpoint history and rollback
- Both sync and async execution
"""

import logging
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver
from infra.config import get_settings

logger = logging.getLogger(__name__)


def get_postgres_checkpointer() -> Optional[PostgresSaver]:
    """
    Initialize and return the official LangGraph PostgreSQL checkpointer.
    
    The PostgresSaver supports both sync and async methods, properly implements
    the CheckpointSaver interface, and handles thread_id semantics correctly.
    
    Returns:
        PostgresSaver instance if enabled, None otherwise
    """
    settings = get_settings()
    if not settings.postgres.enabled:
        logger.info("PostgreSQL checkpointer disabled")
        return None
    
    try:
        # Create PostgresSaver with connection string
        # Official LangGraph implementation handles:
        # - Proper table schema with thread_id, run_id, checkpoint_id
        # - Sync get/put methods compatible with graph.invoke()
        # - Async get_async/put_async for graph.ainvoke()
        # - list() for retrieving all checkpoints
        # - Proper CheckpointTuple structure
        checkpointer = PostgresSaver(
            conn_string=settings.postgres.connection_string
        )
        logger.info(
            f"PostgreSQL checkpointer initialized: {settings.postgres.host}:{settings.postgres.port}"
        )
        return checkpointer
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
        return None


async def get_all_checkpoints_for_session(
    checkpointer: Optional[PostgresSaver], session_id: str
) -> list[dict]:
    """
    Retrieve all checkpoints for a given session (multi-session learning).
    
    Args:
        checkpointer: The PostgresSaver instance
        session_id: The session ID (used as thread_id in LangGraph)
        
    Returns:
        List of checkpoint records
    """
    if not checkpointer:
        return []
    
    try:
        # Use the list() method from PostgresSaver to retrieve checkpoints
        # filtered by thread_id (which maps to session_id)
        checkpoints = await checkpointer.alist(
            config={"configurable": {"thread_id": session_id}}
        )
        return list(checkpoints) if checkpoints else []
    except Exception as e:
        logger.error(f"Failed to retrieve checkpoints for session {session_id}: {e}")
        return []


async def get_all_sessions_by_theme(
    checkpointer: Optional[PostgresSaver], theme: str, limit: int = 10
) -> list[dict]:
    """
    Retrieve checkpoint history for a specific theme (recurring motifs).
    
    This requires a direct database query since the LangGraph PostgresSaver
    doesn't filter by custom application fields. If you need this feature,
    access the database directly or extend with a custom query.
    
    Args:
        checkpointer: The PostgresSaver instance (not used directly)
        theme: The theme to search for
        limit: Max results
        
    Returns:
        List of checkpoint records (empty in base implementation)
    """
    if not checkpointer:
        return []
    
    logger.warning(
        "get_all_sessions_by_theme() requires direct DB access. "
        "Implement a separate database query if needed for theme-based filtering."
    )
    return []
