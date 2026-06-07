from agents.poet_agents import create_all_poet_agents
from infra.langfuse import get_langfuse_client

agents = create_all_poet_agents()

def poet_turn_node(state: MushairaState) -> dict:
    pos = state["current_position"]
    poet_key = RECITATION_ORDER[pos - 1]
    agent = agents[poet_key]

    # Langfuse span wraps the compose call
    lf = get_langfuse_client()
    with lf.span(name=f"poet_turn_{agent.poet_profile.name}") as span:
        verse = agent.compose_poetry(
            theme=state["theme"],
            previous_sher=state.get("previous_sher"),
        )
        span.update(output=verse.__dict__)

    sher_text = f"{verse.urdu}\n{verse.transliteration}"
    return {
        "previous_sher": sher_text,
        "verses": state["verses"] + [verse.__dict__],
        "current_position": pos + 1,
    }

def finalize_node(state: MushairaState) -> dict:
    return {"status": "completed"}
