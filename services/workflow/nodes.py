"""
Graph nodes for the Urdu Mushaira workflow.
"""

from agents.poet_agents import create_all_poet_agents
from agents.base_agent import PoetCompositionError
from agents.poet_config import RECITATION_ORDER
from infra.langfuse import get_langfuse_client
from services.workflow.state import MushairaState

# Agents are module-level singletons so their _conversation memory persists
# across the whole mushaira session (reset between sessions via reset_memory()).
agents = create_all_poet_agents()


def poet_turn_node(state: MushairaState) -> dict:
    """
    One poet's turn.  Passes the full verse arc so the poet can engage
    in genuine literary conversation with everything recited before them.

    On PoetCompositionError: marks the poet as failed in state and signals
    the edge to decide whether to skip or abort — does NOT raise.
    """
    # nodes.py
def poet_turn_node(state: MushairaState) -> dict:
    pos = state["current_position"]
    poet_key = RECITATION_ORDER[pos - 1]
    agent = agents[poet_key]

    # Read this poet's conversation history from graph state
    poet_conversations = state.get("poet_conversations", {})
    prior_responses = poet_conversations.get(poet_key, [])

    verse, raw_response = agent.compose_poetry(
        theme=state["theme"],
        all_verses=state["verses"],
        prior_responses=prior_responses,   # injected — agent doesn't own this
    )

    # Write the new response back into graph state
    updated_conversations = {
        **poet_conversations,
        poet_key: prior_responses + [raw_response],   # append, never mutate
    }

    return {
        "verses": state["verses"] + [verse.__dict__],
        "poet_conversations": updated_conversations,  # graph owns the memory
        "current_position": pos + 1,
        "retry_count": 0,
        "error": None,
    }
    except PoetCompositionError as e:
        return {
            "status": "failed",
            "error": str(e),
            "failed_poets": state.get("failed_poets", []) + [agent.poet_profile.name],
            # Do NOT advance current_position — the edge will decide to skip
        }


def skip_poet_node(state: MushairaState) -> dict:
    """
    Called when a poet has failed and the edge has decided to skip them.
    Advances position so the mushaira continues with the next poet.
    """
    return {
        "current_position": state["current_position"] + 1,
        "status": "running",
        "retry_count": 0,
    }


def finalize_node(state: MushairaState) -> dict:
    """
    Closes the mushaira.  Resets agent memory so the next session starts fresh.
    A summary / closing reflection could be generated here.
    """
    
    skipped = state.get("failed_poets", [])
    return {
        "status": "completed",
        "error": f"Skipped poets: {skipped}" if skipped else None,
    }
