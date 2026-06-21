from typing import TypedDict, List, Optional, Dict, Annotated
from enum import Enum
import operator

class WorkflowStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class PoetStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class MushairaState(TypedDict):
    session_id: str
    theme: str
    current_position: int          # 1–7, which poet's turn
    verses: Annotated[List[dict], operator.add]
    status: str                    # "running" | "completed" | "failed"
    error: Optional[str]
    failed_poets: Annotated[List[str], operator.add]
    poet_conversations: Dict[str, List[dict]] # key: poet_key, value: list of message dicts
    poet_errors: Dict[str, str]    # key: poet_name, value: error message
    skipped_poets: Annotated[List[str], operator.add]
    failed_poets_positions: Annotated[List[int], operator.add]
    current_poet_retry_count: int
