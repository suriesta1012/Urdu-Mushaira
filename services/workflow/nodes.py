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
    pos = state["current_position"]
    poet_key = RECITATION_ORDER[pos - 1]
    agent = agents[poet_key]

    lf = get_langfuse_client()
    try:
        with lf.span(name=f"poet_turn_{agent.poet_profile.name}") as span:
            verse = agent.compose_poetry(
                theme=state["theme"],
                all_verses=state["verses"],   # full arc — every sher so far
            )
            span.update(output=verse.__dict__)

        return {
            "verses": state["verses"] + [verse.__dict__],
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
    for agent in agents.values():
        agent.reset_memory()

    skipped = state.get("failed_poets", [])
    return {
        "status": "completed",
        "error": f"Skipped poets: {skipped}" if skipped else None,
    }
