"""Enhanced Langfuse integration with per-node tracing and token counting."""

import logging
from datetime import datetime
from typing import Optional

from langfuse import Langfuse
from langfuse.decorators import observe

from infra.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[Langfuse] = None


def get_langfuse_client() -> Optional[Langfuse]:
    """Get or initialize Langfuse client. Returns None if disabled."""
    global _client
    
    settings = get_settings()
    if not settings.langfuse.enabled:
        return None
    
    if _client is None:
        if not settings.langfuse.public_key or not settings.langfuse.secret_key:
            logger.warning(
                "Langfuse enabled but missing credentials. "
                "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracing."
            )
            return None
        
        try:
            _client = Langfuse(
                public_key=settings.langfuse.public_key,
                secret_key=settings.langfuse.secret_key,
                host=settings.langfuse.host,
                flush_at=settings.langfuse.flush_at,
                flush_interval=settings.langfuse.flush_interval,
                max_retries=settings.langfuse.max_retries,
                timeout=settings.langfuse.timeout,
                debug=settings.langfuse.debug,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            return None
    
    return _client


def trace_mushaira_session(session_id: str, theme: str):
    """
    Create a top-level Langfuse trace for the whole session.
    
    Args:
        session_id: Unique session identifier
        theme: Mushaira theme
        
    Returns:
        Trace object or mock if Langfuse disabled
    """
    lf = get_langfuse_client()
    if lf is None:
        # Return a mock trace object that safely ignores calls
        return MockTrace()
    
    return lf.trace(
        name="mushaira_session",
        id=session_id,
        metadata={
            "theme": theme,
            "created_at": datetime.utcnow().isoformat(),
        },
    )


def trace_poet_turn(trace, poet_name: str, position: int):
    """
    Trace a single poet's turn within a session.
    
    Args:
        trace: Parent trace object
        poet_name: Name of the poet
        position: Position in recitation order (1-7)
    """
    if not trace or isinstance(trace, MockTrace):
        return MockSpan()
    
    return trace.span(
        name=f"poet_turn_{position}",
        metadata={
            "poet": poet_name,
            "position": position,
        },
    )


def trace_validation(trace, verse_form: str, valid: bool):
    """
    Trace verse validation step.
    
    Args:
        trace: Parent trace object
        verse_form: Form of verse (sher/ghazal/nazm)
        valid: Whether validation passed
    """
    if not trace or isinstance(trace, MockTrace):
        return MockSpan()
    
    return trace.span(
        name="verse_validation",
        metadata={
            "form": verse_form,
            "valid": valid,
        },
    )


class MockTrace:
    """Mock trace object for when Langfuse is disabled."""
    
    def span(self, **kwargs):
        return MockSpan()
    
    def update(self, **kwargs):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


class MockSpan:
    """Mock span object for when Langfuse is disabled."""
    
    def update(self, **kwargs):
        pass
    
    def end(self, **kwargs):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
