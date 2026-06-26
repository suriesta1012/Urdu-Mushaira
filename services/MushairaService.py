 import uuid

from services.workflow.graph import mushaira_graph
from infra.langfuse import trace_mushaira_session


class MushairaService:
    """Application service responsible for running a mushaira."""

    def run(self, theme: str) -> dict:
        session_id = str(uuid.uuid4())

        trace = trace_mushaira_session(
            session_id=session_id,
            theme=theme,
        )

        initial_state = {
            "session_id": session_id,
            "theme": theme,
            "current_position": 1,
            "verses": [],
            "status": "running",
            "error": None,
            "failed_poets": [],
            "poet_conversations": {},
            "poet_errors": {},
            "skipped_poets": [],
            "failed_poets_positions": [],
            "current_poet_retry_count": 0,
            "draft_verse": None,
            "pending_poet_key": None,
            "validation_passed": False,
            "validation_error": None,
        }

        try:
            final_state = mushaira_graph.invoke(initial_state)

            trace.update(
                output={
                    "verse_count": len(final_state["verses"])
                }
            )

            return final_state

        except Exception as e:
            trace.update(
                level="ERROR",
                status_message=str(e),
            )
            raise
