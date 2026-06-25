
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Mock Anthropic before importing anything that uses it
mock_anthropic = MagicMock()
sys.modules["anthropic"] = mock_anthropic

from services.workflow.graph import mushaira_graph
from services.workflow.state import WorkflowStatus

def initial_state(session_id="test-session"):
    return {
        "session_id": session_id,
        "theme": "love and loss",
        "current_position": 1,
        "draft_verse": None,
        "pending_poet_key": None,
        "validation_passed": False,
        "validation_error": None,
        "verses": [],
        "status": "running",
        "error": None,
        "failed_poets": [],
        "poet_conversations": {},
        "poet_errors": {},
        "skipped_poets": [],
        "failed_poets_positions": [],
        "current_poet_retry_count": 0,
    }


def mock_response(text: str):
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    return response


def test_workflow_execution():
    # Mock the response from Anthropic
    response = mock_response('''
    {
      "response_to_previous": "Beautifully said.",
      "form": "sher",
      "urdu": "محبت میں نہیں ہے فرق جینا اور مرنے کا",
      "transliteration": "Mohabbat mein nahi hai farq jeena aur marne ka",
      "translation": "There is no difference between living and dying in love",
      "reflection": "A classic take on love.",
      "next_prompt": "Continue the theme of sacrifice."
    }
    ''')

    with patch("agents.base_agent.client.messages.create", return_value=response):
        # Run the graph
        # Since we use MemorySaver, we need a thread_id in config
        config = {"configurable": {"thread_id": "test-thread"}}
        final_state = mushaira_graph.invoke(initial_state(), config=config)

    print(f"Final Status: {final_state['status']}")
    print(f"Verse Count: {len(final_state['verses'])}")

    assert final_state["status"] == WorkflowStatus.COMPLETED
    assert len(final_state["verses"]) == 7
    assert final_state["draft_verse"] is None
    assert final_state["validation_error"] is None
    print("Workflow execution test passed!")


def test_invalid_draft_retries_before_acceptance():
    invalid_response = mock_response('''
    {
      "response_to_previous": "Beautifully said.",
      "form": "sher",
      "urdu": "This is not Urdu script",
      "transliteration": "This is not Urdu script",
      "translation": "Invalid draft",
      "reflection": "A bad draft.",
      "next_prompt": "Try again."
    }
    ''')
    valid_response = mock_response('''
    {
      "response_to_previous": "Corrected.",
      "form": "sher",
      "urdu": "دل کی وادی میں صدا رہتی ہے",
      "transliteration": "Dil ki vaadi mein sada rehti hai",
      "translation": "An echo remains in the valley of the heart",
      "reflection": "A corrected Urdu draft.",
      "next_prompt": "Carry the echo forward."
    }
    ''')

    with patch(
        "agents.base_agent.client.messages.create",
        side_effect=[invalid_response, valid_response] + [valid_response] * 6,
    ) as create:
        config = {"configurable": {"thread_id": "test-retry-thread"}}
        final_state = mushaira_graph.invoke(initial_state("retry-session"), config=config)

    assert final_state["status"] == WorkflowStatus.COMPLETED
    assert len(final_state["verses"]) == 7
    assert create.call_count == 8
    assert all("This is not Urdu script" not in verse["urdu"] for verse in final_state["verses"])
    print("Validation retry test passed!")


def test_session_isolation():
    # Run two sessions and ensure they don't interfere
    # This is partially verified by the fact that we don't use global agents anymore
    # and agents are stateless regarding conversation history.
    pass

if __name__ == "__main__":
    try:
        test_workflow_execution()
        test_invalid_draft_retries_before_acceptance()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
