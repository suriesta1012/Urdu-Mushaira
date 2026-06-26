"""
Graph nodes for the Urdu Mushaira workflow.
"""

from agents.poet_agents import create_all_poet_agents
from agents.base_agent import PoetCompositionError
from agents.poet_config import RECITATION_ORDER
from services.workflow.state import MushairaState, WorkflowStatus


def _has_urdu_script(value: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in value)


def _validate_draft_verse(verse: dict) -> list[str]:
    errors: list[str] = []
    required_fields = [
        "form",
        "urdu",
        "transliteration",
        "translation",
        "reflection",
        "next_prompt",
        "poet_name",
        "poet_urdu_name",
    ]

    for field in required_fields:
        if not str(verse.get(field, "")).strip():
            errors.append(f"{field} is required")

    if verse.get("form") not in {"sher", "ghazal", "nazm"}:
        errors.append("form must be one of: sher, ghazal, nazm")

    urdu = str(verse.get("urdu", ""))
    if urdu and not _has_urdu_script(urdu):
        errors.append("urdu must contain Urdu script")

    return errors


def poet_turn_node(state: MushairaState) -> dict:
    """
    One poet's turn.  Passes the full verse arc so the poet can engage
    in genuine literary conversation with everything recited before them.

    On PoetCompositionError: records a graph-visible error so the edge can
    decide whether to retry, skip, or abort.
    """
    pos = state["current_position"]
    poet_key = RECITATION_ORDER[pos - 1]

    # Create agents locally to ensure session isolation
    agents = create_all_poet_agents()
    agent = agents[poet_key]

    # Read this poet's conversation history from graph state
    poet_conversations = state.get("poet_conversations", {})
    prior_responses = poet_conversations.get(poet_key, [])
    
    try:
        verse, raw_response, user_message = agent.compose_poetry(
            theme=state["theme"],
            all_verses=state["verses"],
            conversation_history=prior_responses,
            max_retries=1,
        )
        
        # Build update to the conversation history
        new_history = prior_responses + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": raw_response}
        ]

        updated_conversations = {
            **state.get("poet_conversations", {}),
            poet_key: new_history,
        }
        
        return {
            "draft_verse": verse.__dict__,
            "pending_poet_key": poet_key,
            "validation_passed": False,
            "validation_error": None,
            "error": None,
            "poet_conversations": updated_conversations,
            "current_poet_retry_count": 0,
            "status": WorkflowStatus.RUNNING,
        }
    except PoetCompositionError as e:
        poet_name = agent.poet_profile.name
        new_errors = {**state.get("poet_errors", {}), poet_name: str(e)}
        
        return {
            "draft_verse": None,
            "pending_poet_key": poet_key,
            "validation_passed": False,
            "validation_error": None,
            "error": str(e),
            "poet_errors": new_errors,
            "current_poet_retry_count": state.get("current_poet_retry_count", 0) + 1,
            "status": WorkflowStatus.RUNNING,
        }


def validate_verse_node(state: MushairaState) -> dict:
    """
    Validates the generated draft before it can enter the public verse list.
    """
    draft = state.get("draft_verse")
    if not draft:
        return {
            "validation_passed": False,
            "validation_error": "No draft verse was generated",
            "current_poet_retry_count": state.get("current_poet_retry_count", 0) + 1,
            "status": WorkflowStatus.RUNNING,
        }

    errors = _validate_draft_verse(draft)
    if errors:
        error_message = "; ".join(errors)
        poet_name = draft.get("poet_name") or state.get("pending_poet_key") or "unknown"
        new_errors = {**state.get("poet_errors", {}), poet_name: error_message}
        return {
            "validation_passed": False,
            "validation_error": error_message,
            "error": error_message,
            "poet_errors": new_errors,
            "current_poet_retry_count": state.get("current_poet_retry_count", 0) + 1,
            "status": WorkflowStatus.RUNNING,
        }

    return {
        "validation_passed": True,
        "validation_error": None,
        "error": None,
        "status": WorkflowStatus.RUNNING,
    }


def accept_verse_node(state: MushairaState) -> dict:
    """
    Commits a validated draft verse to the mushaira and advances to the next poet.
    """
    draft = state.get("draft_verse")
    return {
        "verses": [draft] if draft else [],
        "draft_verse": None,
        "pending_poet_key": None,
        "validation_passed": False,
        "validation_error": None,
        "error": None,
        "current_position": state["current_position"] + 1,
        "current_poet_retry_count": 0,
        "status": WorkflowStatus.RUNNING,
    }


def skip_poet_node(state: MushairaState) -> dict:
    """
    Called when a poet has failed and the edge has decided to skip them.
    Advances position so the mushaira continues with the next poet.
    """
    poet_key = RECITATION_ORDER[state["current_position"] - 1]
    poet_name = poet_key.replace("_", " ").title()
    return {
        "draft_verse": None,
        "pending_poet_key": None,
        "validation_passed": False,
        "validation_error": None,
        "error": None,
        "current_position": state["current_position"] + 1,
        "failed_poets": [poet_name],
        "failed_poets_positions": [state["current_position"]],
        "skipped_poets": [poet_key], # reducer will add to list
        "current_poet_retry_count": 0,
        "status": WorkflowStatus.RUNNING,
    }


def finalize_node(state: MushairaState) -> dict:
    """
    Closes the mushaira.
    """
    return {
        "status": WorkflowStatus.COMPLETED,
    }


    # Read this poet's conversation history from graph state
    poet_conversations = state.get("poet_conversations", {})
    prior_responses = poet_conversations.get(poet_key, [])
    
    try:
        verse, raw_response, user_message = agent.compose_poetry(
            theme=state["theme"],
            all_verses=state["verses"],
            conversation_history=prior_responses,
        )
        
        # Build update to the conversation history
        new_history = prior_responses + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": raw_response}
        ]

        updated_conversations = {
            **state.get("poet_conversations", {}),
            poet_key: new_history,
        }
        
        return {
            "verses": [verse.__dict__], # reducer will add to list
            "poet_conversations": updated_conversations,
            "current_position": pos + 1,
            "current_poet_retry_count": 0,
            "status": WorkflowStatus.RUNNING,
        }
    except PoetCompositionError as e:
        # Record the error but don't advance position
        poet_name = agent.poet_profile.name
        new_errors = {**state.get("poet_errors", {}), poet_name: str(e)}
        
        return {
            "failed_poets": [poet_name], # reducer will add to list
            "failed_poets_positions": [pos], # reducer will add to list
            "poet_errors": new_errors,
            "current_poet_retry_count": 0,
            "status": WorkflowStatus.RUNNING,
        }

