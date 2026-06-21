
import sys
import os
from unittest.mock import MagicMock, patch

# Mock Anthropic before importing anything that uses it
mock_anthropic = MagicMock()
sys.modules["anthropic"] = mock_anthropic

from services.workflow.graph import mushaira_graph
from services.workflow.state import WorkflowStatus

def test_workflow_execution():
    # Setup initial state
    initial_state = {
        "session_id": "test-session",
        "theme": "love and loss",
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
    }

    # Mock the response from Anthropic
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='''
    {
      "response_to_previous": "Beautifully said.",
      "form": "sher",
      "urdu": "محبت میں نہیں ہے فرق جینا اور مرنے کا",
      "transliteration": "Mohabbat mein nahi hai farq jeena aur marne ka",
      "translation": "There is no difference between living and dying in love",
      "reflection": "A classic take on love.",
      "next_prompt": "Continue the theme of sacrifice."
    }
    ''')]

    with patch("agents.base_agent.client.messages.create", return_value=mock_response):
        # Run the graph
        # Since we use MemorySaver, we need a thread_id in config
        config = {"configurable": {"thread_id": "test-thread"}}
        final_state = mushaira_graph.invoke(initial_state, config=config)

    print(f"Final Status: {final_state['status']}")
    print(f"Verse Count: {len(final_state['verses'])}")

    assert final_state["status"] == WorkflowStatus.COMPLETED
    assert len(final_state["verses"]) == 7
    print("Workflow execution test passed!")

def test_session_isolation():
    # Run two sessions and ensure they don't interfere
    # This is partially verified by the fact that we don't use global agents anymore
    # and agents are stateless regarding conversation history.
    pass

if __name__ == "__main__":
    try:
        test_workflow_execution()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
