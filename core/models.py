"""
Core data models for Urdu Mushaira system.
Defines all persistent structures used across orchestration, state management, and outputs.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json
import uuid


class MushairaStatus(Enum):
    """Lifecycle states of a mushaira"""
    PENDING = "pending"           # Created, not started
    RUNNING = "running"           # Currently executing
    COMPLETED = "completed"       # All poets recited
    FAILED = "failed"            # Unrecoverable error
    PAUSED = "paused"            # Temporarily halted


class PoetTurnStatus(Enum):
    """Lifecycle states of individual poet turns"""
    WAITING = "waiting"           # Waiting for their turn
    IN_PROGRESS = "in_progress"   # Currently composing
    COMPLETED = "completed"       # Verse generated successfully
    RETRY = "retry"              # Failed, retrying
    FAILED = "failed"            # Gave up after max retries


@dataclass
class SinglePoetryOutput:
    """Output from a single poet's turn in the mushaira"""
    poet_name: str
    poet_urdu_name: str
    position: int                 # 1-7 in recitation order
    form: str                     # sher | ghazal | nazm
    urdu: str                     # Verse in Urdu script
    transliteration: str          # Roman Urdu
    translation: str              # English meaning
    reflection: str               # Mood/imagery note
    next_prompt: str              # Theme baton for next poet
    
    # Metadata
    status: PoetTurnStatus = PoetTurnStatus.COMPLETED
    timestamp: datetime = field(default_factory=datetime.now)
    model_used: str = "claude-sonnet-4-20250514"
    tokens_used: int = 0          # Completion tokens
    latency_ms: float = 0.0       # API response time
    
    # Retrieval context
    retrieved_context: List[str] = field(default_factory=list)
    retrieved_count: int = 0
    
    # Error tracking
    attempts: int = 1
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling datetime and enum serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class MushairaSession:
    """Complete session of a mushaira with all poet contributions"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Metadata
    theme: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # State
    status: MushairaStatus = MushairaStatus.PENDING
    current_poet_position: int = 0  # 0 = not started, 1-7 = current poet
    
    # Configuration
    model: str = "claude-sonnet-4-20250514"
    max_retries_per_poet: int = 3
    temperature: float = 0.8
    
    # Outputs and tracking
    poet_outputs: List[SinglePoetryOutput] = field(default_factory=list)
    errors_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metrics
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    
    def add_poet_output(self, output: SinglePoetryOutput) -> None:
        """Add a poet's output and update session state"""
        self.poet_outputs.append(output)
        self.total_tokens_used += output.tokens_used
        self.total_latency_ms += output.latency_ms
        self.current_poet_position = output.position
    
    def add_error(self, poet_name: str, error: str, context: Optional[Dict] = None) -> None:
        """Log an error during mushaira execution"""
        self.errors_log.append({
            "timestamp": datetime.now().isoformat(),
            "poet_name": poet_name,
            "error": error,
            "context": context or {}
        })
    
    def get_previous_verse(self) -> Optional[str]:
        """Get the previous poet's verse as context for next poet"""
        if not self.poet_outputs:
            return None
        last_output = self.poet_outputs[-1]
        return f"{last_output.urdu}\n({last_output.transliteration})"
    
    def is_complete(self) -> bool:
        """Check if all 7 poets have recited"""
        return len(self.poet_outputs) == 7 and all(
            p.status == PoetTurnStatus.COMPLETED for p in self.poet_outputs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "theme": self.theme,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "current_poet_position": self.current_poet_position,
            "model": self.model,
            "max_retries_per_poet": self.max_retries_per_poet,
            "temperature": self.temperature,
            "poet_outputs": [p.to_dict() for p in self.poet_outputs],
            "errors_log": self.errors_log,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "total_latency_ms": self.total_latency_ms,
            "is_complete": self.is_complete(),
        }


@dataclass
class MushairaTranscript:
    """Formatted transcript of a completed mushaira (for output/display)"""
    session_id: str
    theme: str
    created_at: datetime
    
    # Formatted content
    verses: List[Dict[str, str]] = field(default_factory=list)  # [{"poet": name, "urdu": ..., "trans": ..., "eng": ...}]
    
    # Metadata
    session_metadata: Optional[Dict[str, Any]] = None
    
    def add_verse(self, poet_name: str, urdu: str, transliteration: str, translation: str) -> None:
        """Add a formatted verse to transcript"""
        self.verses.append({
            "poet": poet_name,
            "urdu": urdu,
            "transliteration": transliteration,
            "translation": translation,
        })
    
    def to_markdown(self) -> str:
        """Export transcript as formatted Markdown"""
        lines = [
            f"# Urdu Mushaira: {self.theme}",
            f"**Date:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Session ID:** {self.session_id}",
            "",
        ]
        
        for i, verse in enumerate(self.verses, 1):
            lines.extend([
                f"## {i}. {verse['poet']}",
                "",
                f"**Urdu:**",
                f"> {verse['urdu']}",
                "",
                f"**Transliteration:**",
                f"> {verse['transliteration']}",
                "",
                f"**Translation:**",
                f"> {verse['translation']}",
                "",
            ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transcript to dictionary"""
        return {
            "session_id": self.session_id,
            "theme": self.theme,
            "created_at": self.created_at.isoformat(),
            "verses": self.verses,
            "session_metadata": self.session_metadata,
        }


@dataclass
class CompletionMetrics:
    """Metrics collected during a single API call"""
    tokens_used: int
    latency_ms: float
    model: str
    success: bool
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
