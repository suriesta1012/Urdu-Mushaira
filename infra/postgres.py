"""
PostgreSQL Checkpointer for LangGraph.

Enables multi-session learning by persisting graph state across sessions.
Stores checkpoints in Postgres, allowing recovery and state inspection.
"""

import json
import logging
from typing import Optional, Sequence
from datetime import datetime

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from psycopg import AsyncConnection, connect
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class PostgresCheckpointer(BaseCheckpointSaver):
    """
    LangGraph CheckpointSaver backed by PostgreSQL.
    
    Supports:
    - Persisting graph state across sessions
    - Multi-session learning (retrieve prior poet behaviors, themes)
    - Session recovery on failure
    - Checkpoint history and rollback
    """

    def __init__(self, connection_string: str, table_name: str = "langgraph_checkpoints"):
        """
        Initialize PostgreSQL checkpointer.
        
        Args:
            connection_string: psycopg3 connection string (e.g., "postgresql://user:password@localhost/db")
            table_name: Name of the checkpoint table
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self._initialized = False

    async def _ensure_table(self, conn: AsyncConnection) -> None:
        """Create checkpoint table if it doesn't exist."""
        if self._initialized:
            return

        async with conn.cursor() as cur:
            await cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    session_id TEXT,
                    theme TEXT,
                    status TEXT DEFAULT 'running',
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, checkpoint_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_session_id ON {self.table_name}(session_id);
                CREATE INDEX IF NOT EXISTS idx_theme ON {self.table_name}(theme);
                CREATE INDEX IF NOT EXISTS idx_created_at ON {self.table_name}(created_at);
            """)
            await conn.commit()
            self._initialized = True

    async def put(self, config: dict, values: dict, metadata: dict) -> None:
        """
        Save a checkpoint.
        
        Args:
            config: LangGraph config (contains thread_id)
            values: The graph state to checkpoint
            metadata: Metadata about this checkpoint
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = metadata.get("checkpoint_id", datetime.utcnow().isoformat())
        
        async with await connect(self.connection_string) as conn:
            await self._ensure_table(conn)
            
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    INSERT INTO {self.table_name} 
                    (thread_id, checkpoint_id, session_id, theme, status, data, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (thread_id, checkpoint_id)
                    DO UPDATE SET data = EXCLUDED.data, updated_at = CURRENT_TIMESTAMP;
                """, (
                    thread_id,
                    checkpoint_id,
                    values.get("session_id"),
                    values.get("theme"),
                    values.get("status", "running"),
                    json.dumps(values, default=str),
                ))
            await conn.commit()

    async def get(self, config: dict, checkpoint_id: Optional[str] = None) -> Optional[CheckpointTuple]:
        """
        Retrieve a checkpoint.
        
        Args:
            config: LangGraph config (contains thread_id)
            checkpoint_id: Optional specific checkpoint ID; if None, returns latest
            
        Returns:
            CheckpointTuple or None
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        
        async with await connect(self.connection_string) as conn:
            await self._ensure_table(conn)
            
            async with conn.cursor(row_factory=dict_row) as cur:
                if checkpoint_id:
                    await cur.execute(f"""
                        SELECT data FROM {self.table_name}
                        WHERE thread_id = %s AND checkpoint_id = %s;
                    """, (thread_id, checkpoint_id))
                else:
                    await cur.execute(f"""
                        SELECT data FROM {self.table_name}
                        WHERE thread_id = %s
                        ORDER BY updated_at DESC
                        LIMIT 1;
                    """, (thread_id,))
                
                row = await cur.fetchone()
                if row:
                    return CheckpointTuple(
                        config=config,
                        checkpoint=json.loads(row["data"])
                    )
        return None

    async def get_all_checkpoints_for_session(self, session_id: str) -> list[dict]:
        """
        Retrieve all checkpoints for a given session (multi-session learning).
        
        Args:
            session_id: The session ID to query
            
        Returns:
            List of checkpoint records
        """
        async with await connect(self.connection_string) as conn:
            await self._ensure_table(conn)
            
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(f"""
                    SELECT thread_id, checkpoint_id, session_id, theme, status, 
                           created_at, updated_at
                    FROM {self.table_name}
                    WHERE session_id = %s
                    ORDER BY created_at DESC;
                """, (session_id,))
                
                return await cur.fetchall()

    async def get_all_sessions_by_theme(self, theme: str, limit: int = 10) -> list[dict]:
        """
        Retrieve checkpoint history for a specific theme (recurring motifs).
        
        Args:
            theme: The theme to search for
            limit: Max results
            
        Returns:
            List of checkpoint records
        """
        async with await connect(self.connection_string) as conn:
            await self._ensure_table(conn)
            
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(f"""
                    SELECT DISTINCT ON (session_id) 
                           thread_id, checkpoint_id, session_id, theme, 
                           status, created_at
                    FROM {self.table_name}
                    WHERE theme = %s AND status = 'completed'
                    ORDER BY session_id, created_at DESC
                    LIMIT %s;
                """, (theme, limit))
                
                return await cur.fetchall()
