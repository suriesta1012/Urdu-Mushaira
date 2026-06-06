"""
Persistence layer for Urdu Mushaira.
Handles all disk I/O, state storage, and session recovery.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import sqlite3

from core.models import MushairaSession, SinglePoetryOutput, MushairaTranscript, MushairaStatus, PoetTurnStatus


class StorageConfig:
    """Configuration for storage locations"""
    def __init__(self, base_dir: str = "./data"):
        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.outputs_dir = self.base_dir / "outputs"
        self.transcripts_dir = self.base_dir / "transcripts"
        self.db_path = self.base_dir / "mushaira.db"
        
        # Create directories
        for d in [self.sessions_dir, self.outputs_dir, self.transcripts_dir]:
            d.mkdir(parents=True, exist_ok=True)


class SessionStore:
    """
    Manages session persistence to disk + SQLite.
    Every session is:
      1. Saved to JSON for manual inspection
      2. Indexed in SQLite for querying
    """
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self._init_db()
    
    def _init_db(self) -> None:
        """Create SQLite tables if they don't exist"""
        conn = sqlite3.connect(str(self.config.db_path))
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                theme TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                total_tokens_used INTEGER,
                total_cost_usd REAL,
                total_latency_ms REAL,
                poet_count INTEGER,
                model TEXT
            )
        """)
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS poet_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                poet_name TEXT NOT NULL,
                position INTEGER NOT NULL,
                status TEXT NOT NULL,
                tokens_used INTEGER,
                latency_ms REAL,
                attempts INTEGER,
                timestamp TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_session(self, session: MushairaSession) -> str:
        """
        Save session to JSON and index in DB.
        Returns: path to saved file
        """
        session_file = self.config.sessions_dir / f"{session.session_id}.json"
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Index in DB
        self._index_session(session)
        
        return str(session_file)
    
    def _index_session(self, session: MushairaSession) -> None:
        """Add session metadata to SQLite"""
        conn = sqlite3.connect(str(self.config.db_path))
        c = conn.cursor()
        
        c.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_id, theme, status, created_at, started_at, completed_at, 
             total_tokens_used, total_cost_usd, total_latency_ms, poet_count, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.theme,
            session.status.value,
            session.created_at.isoformat(),
            session.started_at.isoformat() if session.started_at else None,
            session.completed_at.isoformat() if session.completed_at else None,
            session.total_tokens_used,
            session.total_cost_usd,
            session.total_latency_ms,
            len(session.poet_outputs),
            session.model,
        ))
        
        # Index poet turns
        for output in session.poet_outputs:
            c.execute("""
                INSERT OR REPLACE INTO poet_turns
                (session_id, poet_name, position, status, tokens_used, latency_ms, attempts, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                output.poet_name,
                output.position,
                output.status.value,
                output.tokens_used,
                output.latency_ms,
                output.attempts,
                output.timestamp.isoformat(),
            ))
        
        conn.commit()
        conn.close()
    
    def load_session(self, session_id: str) -> Optional[MushairaSession]:
        """Load a session from disk"""
        session_file = self.config.sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct session
        session = MushairaSession(
            session_id=data['session_id'],
            theme=data['theme'],
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
            status=MushairaStatus(data['status']),
            current_poet_position=data['current_poet_position'],
            model=data['model'],
            max_retries_per_poet=data['max_retries_per_poet'],
            temperature=data['temperature'],
            total_tokens_used=data['total_tokens_used'],
            total_cost_usd=data['total_cost_usd'],
            total_latency_ms=data['total_latency_ms'],
        )
        
        # Reconstruct poet outputs
        for output_data in data['poet_outputs']:
            output = SinglePoetryOutput(
                poet_name=output_data['poet_name'],
                poet_urdu_name=output_data['poet_urdu_name'],
                position=output_data['position'],
                form=output_data['form'],
                urdu=output_data['urdu'],
                transliteration=output_data['transliteration'],
                translation=output_data['translation'],
                reflection=output_data['reflection'],
                next_prompt=output_data['next_prompt'],
                status=PoetTurnStatus(output_data['status']),
                timestamp=datetime.fromisoformat(output_data['timestamp']),
                model_used=output_data['model_used'],
                tokens_used=output_data['tokens_used'],
                latency_ms=output_data['latency_ms'],
                retrieved_context=output_data['retrieved_context'],
                retrieved_count=output_data['retrieved_count'],
                attempts=output_data['attempts'],
                error_message=output_data['error_message'],
            )
            session.poet_outputs.append(output)
        
        session.errors_log = data['errors_log']
        
        return session
    
    def list_sessions(self, limit: int = 20, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recent sessions from DB"""
        conn = sqlite3.connect(str(self.config.db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM sessions"
        if status_filter:
            query += f" WHERE status = '{status_filter}'"
        query += " ORDER BY created_at DESC LIMIT ?"
        
        c.execute(query, (limit,))
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def query_sessions_by_theme(self, theme: str) -> List[Dict[str, Any]]:
        """Find all sessions for a given theme"""
        conn = sqlite3.connect(str(self.config.db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM sessions WHERE theme LIKE ? ORDER BY created_at DESC", (f"%{theme}%",))
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics"""
        conn = sqlite3.connect(str(self.config.db_path))
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) as total_sessions FROM sessions")
        total_sessions = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) as completed_sessions FROM sessions WHERE status = 'completed'")
        completed_sessions = c.fetchone()[0]
        
        c.execute("SELECT SUM(total_tokens_used) as total_tokens FROM sessions")
        total_tokens = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_cost_usd) as total_cost FROM sessions")
        total_cost = c.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": completed_sessions / total_sessions if total_sessions > 0 else 0,
            "total_tokens_used": total_tokens,
            "total_cost_usd": total_cost,
        }


class OutputStore:
    """Manages output files: transcripts, raw JSON, markdown"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
    
    def save_transcript_markdown(self, transcript: MushairaTranscript) -> str:
        """Save formatted transcript as Markdown"""
        filename = f"{transcript.session_id}_transcript.md"
        filepath = self.config.transcripts_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(transcript.to_markdown())
        
        return str(filepath)
    
    def save_transcript_json(self, transcript: MushairaTranscript) -> str:
        """Save transcript as JSON"""
        filename = f"{transcript.session_id}_transcript.json"
        filepath = self.config.transcripts_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript.to_dict(), f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def save_raw_outputs(self, session: MushairaSession) -> str:
        """Save all poet outputs as JSON"""
        filename = f"{session.session_id}_raw_outputs.json"
        filepath = self.config.outputs_dir / filename
        
        outputs = [p.to_dict() for p in session.poet_outputs]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(outputs, f, ensure_ascii=False, indent=2)
        
        return str(filepath)


class CheckpointManager:
    """
    Handles session checkpoints for recovery.
    If a mushaira crashes mid-way, you can resume from the last checkpoint.
    """
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.checkpoint_dir = config.base_dir / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save_checkpoint(self, session: MushairaSession) -> str:
        """Save a checkpoint of current session state"""
        checkpoint_file = self.checkpoint_dir / f"{session.session_id}_checkpoint.json"
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        
        return str(checkpoint_file)
    
    def load_checkpoint(self, session_id: str) -> Optional[MushairaSession]:
        """Load a checkpoint if it exists"""
        checkpoint_file = self.checkpoint_dir / f"{session_id}_checkpoint.json"
        
        if not checkpoint_file.exists():
            return None
        
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct session (same logic as SessionStore.load_session)
        session = MushairaSession(session_id=data['session_id'])
        # ... populate fields from data ...
        
        return session
    
    def remove_checkpoint(self, session_id: str) -> None:
        """Remove checkpoint after successful completion"""
        checkpoint_file = self.checkpoint_dir / f"{session_id}_checkpoint.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
