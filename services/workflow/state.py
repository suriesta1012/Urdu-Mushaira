from typing import TypedDict, List, Optional,Dict
from dataclasses import dataclass
from pydantic import BaseModel

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"  # Unrecoverable (too many poets failed)

class PoetStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"  # Will be skipped
    SKIPPED = "skipped"
class MushairaState(BaseModel):
    session_id: str
    theme: str
    current_position: int          # 1–7, which poet's turn
    previous_sher: Optional[str]   # last recited verse (Urdu + transliteration)
    verses: List[dict]             # all PoetryData dicts accumulated so far
    status: str                    # "running" | "completed" | "failed"
    error: Optional[str]
    retry_count:int
    failed_poets:List[str]
    poet_conversations: Dict[str, List[str]]
