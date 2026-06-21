"""
Graph nodes for the Urdu Mushaira workflow.
"""

from agents.poet_agents import create_all_poet_agents
from agents.base_agent import PoetCompositionError
from agents.poet_config import RECITATION_ORDER
from services.workflow.state import MushairaState, WorkflowStatus


def poet_turn_node(state: MushairaState) -> dict:
    """
    One poet's turn.  Passes the full verse arc so the poet can engage
    in genuine literary conversation with everything recited before them.

    On PoetCompositionError: marks the poet as failed in state and signals
    the edge to decide whether to skip or abort — does NOT raise.
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

def skip_poet_node(state: MushairaState) -> dict:
    """
    Called when a poet has failed and the edge has decided to skip them.
    Advances position so the mushaira continues with the next poet.
    """
    poet_key = RECITATION_ORDER[state["current_position"] - 1]
    return {
        "current_position": state["current_position"] + 1,
        "skipped_poets": [poet_key], # reducer will add to list
        "status": WorkflowStatus.RUNNING,
    }


def finalize_node(state: MushairaState) -> dict:
    """
    Closes the mushaira.
    """
    return {
        "status": WorkflowStatus.COMPLETED,
    }
