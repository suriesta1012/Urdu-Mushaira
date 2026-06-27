from langfuse import Langfuse
import os
from dotenv import load_dotenv 
load_dotenv()

_client: Langfuse | None = None

def get_langfuse_client() -> Langfuse:
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
    return _client

def trace_mushaira_session(session_id: str, theme: str):
    """Create a top-level Langfuse trace for the whole session."""
    lf = get_langfuse_client()
    return lf.trace(
        name="mushaira_session",
        id=session_id,
        metadata={"theme": theme},
    )
