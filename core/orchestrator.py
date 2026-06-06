"""
Main orchestration engine for Urdu Mushaira.
This is the core conductor that orchestrates the 7-poet recitation loop.

Workflow:
  1. Initialize session with theme
  2. For each poet (1-7):
     a. Retrieve context (RAG - if enabled)
     b. Get previous poet's verse
     c. Call poet agent to compose
     d. Parse and validate output
     e. Save checkpoint
     f. Handle errors and retries
  3. Generate outputs (transcripts, metadata)
  4. Clean up
"""

import time
from typing import Optional, Callable
from datetime import datetime

from core.models import (
    MushairaSession,
    MushairaStatus,
    PoetTurnStatus,
    SinglePoetryOutput,
    MushairaTranscript,
)
from core.persistence import SessionStore, OutputStore, CheckpointManager, StorageConfig
from agents.base_agent import BasePoetAgent
from agents.poet_agents import create_all_poet_agents
from agents.poet_config import get_all_poets_in_order


class MushairaOrchestrator:
    """
    Main orchestration engine.
    Coordinates all 7 poet agents through a single mushaira session.
    """
    
    def __init__(
        self,
        theme: str,
        model: str = "claude-sonnet-4-20250514",
        max_retries_per_poet: int = 3,
        temperature: float = 0.8,
        storage_dir: str = "./data",
        enable_checkpoints: bool = True,
    ):
        # Configuration
        self.theme = theme
        self.model = model
        self.max_retries_per_poet = max_retries_per_poet
        self.temperature = temperature
        self.enable_checkpoints = enable_checkpoints
        
        # Storage
        self.storage_config = StorageConfig(base_dir=storage_dir)
        self.session_store = SessionStore(self.storage_config)
        self.output_store = OutputStore(self.storage_config)
        self.checkpoint_manager = CheckpointManager(self.storage_config)
        
        # Agents
        self.agents = create_all_poet_agents()
        self.poets = get_all_poets_in_order()
        
        # Session
        self.session = MushairaSession(
            theme=theme,
            model=model,
            max_retries_per_poet=max_retries_per_poet,
            temperature=temperature,
        )
        
        # Callbacks for progress tracking
        self.on_poet_start: Optional[Callable[[int, str], None]] = None
        self.on_poet_complete: Optional[Callable[[int, str, str], None]] = None
        self.on_error: Optional[Callable[[int, str, str], None]] = None
    
    def run(self) -> MushairaSession:
        """
        Execute the complete mushaira.
        Returns the completed session with all poet outputs.
        """
        print(f"\n🎭 Urdu Mushaira: '{self.theme}'")
        print(f"📜 Session ID: {self.session.session_id}")
        print("=" * 60)
        
        self.session.status = MushairaStatus.RUNNING
        self.session.started_at = datetime.now()
        
        try:
            # Main recitation loop
            for position in range(1, 8):
                self._run_poet_turn(position)
            
            # Mark complete
            self.session.status = MushairaStatus.COMPLETED
            self.session.completed_at = datetime.now()
            self._emit_callback("on_complete")
            
        except Exception as e:
            self.session.status = MushairaStatus.FAILED
            self.session.add_error("ORCHESTRATOR", str(e))
            print(f"\n❌ Mushaira failed: {e}")
            raise
        
        finally:
            # Always save final state
            self.session_store.save_session(self.session)
            if self.enable_checkpoints:
                self.checkpoint_manager.remove_checkpoint(self.session.session_id)
        
        return self.session
    
    def _run_poet_turn(self, position: int) -> None:
        """
        Execute a single poet's turn in the mushaira.
        Handles retrieval, composition, parsing, and error recovery.
        """
        poet_profile = self.poets[position - 1]
        poet_name = poet_profile.name
        
        print(f"\n🎤 Position {position}: {poet_name} ({poet_profile.urdu_name})")
        
        if self.on_poet_start:
            self.on_poet_start(position, poet_name)
        
        # Initialize turn state
        turn_status = PoetTurnStatus.IN_PROGRESS
        error_message = None
        attempt = 0
        
        # Retry loop
        for attempt in range(1, self.max_retries_per_poet + 1):
            try:
                # 1. Get poet agent
                agent = self.agents.get(poet_profile.name.lower().replace(" ", "_"))
                if not agent:
                    raise ValueError(f"Agent not found for {poet_name}")
                
                # 2. Get previous verse for context
                previous_verse = self.session.get_previous_verse()
                
                # 3. Call agent to compose
                start_time = time.time()
                poetry_data = agent.compose_poetry(
                    theme=self.theme,
                    previous_sher=previous_verse,
                    max_retries=1,  # Already in outer retry loop
                )
                latency_ms = (time.time() - start_time) * 1000
                
                # 4. Convert to output model
                output = SinglePoetryOutput(
                    poet_name=poetry_data.poet_name,
                    poet_urdu_name=poetry_data.poet_urdu_name,
                    position=position,
                    form=poetry_data.form,
                    urdu=poetry_data.urdu,
                    transliteration=poetry_data.transliteration,
                    translation=poetry_data.translation,
                    reflection=poetry_data.reflection,
                    next_prompt=poetry_data.next_prompt,
                    status=PoetTurnStatus.COMPLETED,
                    model_used=self.model,
                    latency_ms=latency_ms,
                    retrieved_context=poetry_data.retrieved_context,
                    retrieved_count=len(poetry_data.retrieved_context),
                    attempts=attempt,
                )
                
                # 5. Add to session
                self.session.add_poet_output(output)
                
                # 6. Print output
                print(f"   ✓ Verse composed in {latency_ms:.0f}ms")
                print(f"   📖 Form: {poetry_data.form}")
                print(f"   🔤 Urdu: {poetry_data.urdu}")
                print(f"   💭 {poetry_data.reflection}")
                
                # 7. Checkpoint
                if self.enable_checkpoints:
                    self.checkpoint_manager.save_checkpoint(self.session)
                
                # Success
                turn_status = PoetTurnStatus.COMPLETED
                
                if self.on_poet_complete:
                    self.on_poet_complete(position, poet_name, poetry_data.urdu)
                
                return  # Exit retry loop
            
            except Exception as e:
                error_message = str(e)
                print(f"   ⚠️  Attempt {attempt} failed: {error_message}")
                
                if attempt < self.max_retries_per_poet:
                    turn_status = PoetTurnStatus.RETRY
                    wait_time = 2 ** (attempt - 1)
                    print(f"   ⏳ Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    turn_status = PoetTurnStatus.FAILED
                    if self.on_error:
                        self.on_error(position, poet_name, error_message)
        
        # All retries exhausted
        if turn_status != PoetTurnStatus.COMPLETED:
            self.session.add_error(
                poet_name=poet_name,
                error=f"Failed after {self.max_retries_per_poet} attempts: {error_message}",
                context={"position": position, "attempt": attempt},
            )
            print(f"   ❌ {poet_name} failed permanently")
            raise RuntimeError(f"Poet {poet_name} failed to compose after {self.max_retries_per_poet} attempts")
    
    def _emit_callback(self, callback_name: str) -> None:
        """Emit a callback if registered"""
        callback = getattr(self, callback_name, None)
        if callback and callable(callback):
            callback()
    
    def generate_outputs(self) -> dict:
        """
        Generate all output files from completed session.
        Returns dict with paths to generated files.
        """
        if not self.session.is_complete():
            raise ValueError("Session is not complete. Cannot generate outputs.")
        
        outputs = {}
        
        # 1. Create transcript
        transcript = MushairaTranscript(
            session_id=self.session.session_id,
            theme=self.session.theme,
            created_at=self.session.created_at,
            session_metadata=self.session.to_dict(),
        )
        
        for output in self.session.poet_outputs:
            transcript.add_verse(
                poet_name=output.poet_name,
                urdu=output.urdu,
                transliteration=output.transliteration,
                translation=output.translation,
            )
        
        # 2. Save outputs
        outputs['session_json'] = self.session_store.save_session(self.session)
        outputs['transcript_markdown'] = self.output_store.save_transcript_markdown(transcript)
        outputs['transcript_json'] = self.output_store.save_transcript_json(transcript)
        outputs['raw_outputs'] = self.output_store.save_raw_outputs(self.session)
        
        print("\n✅ Outputs generated:")
        for key, path in outputs.items():
            print(f"   📄 {key}: {path}")
        
        return outputs
    
    def print_summary(self) -> None:
        """Print session summary"""
        print("\n" + "=" * 60)
        print("📊 MUSHAIRA SUMMARY")
        print("=" * 60)
        print(f"Theme: {self.session.theme}")
        print(f"Status: {self.session.status.value.upper()}")
        print(f"Poets: {len(self.session.poet_outputs)}/7")
        print(f"Total tokens: {self.session.total_tokens_used}")
        print(f"Total latency: {self.session.total_latency_ms:.0f}ms")
        
        if self.session.errors_log:
            print(f"\n⚠️  Errors: {len(self.session.errors_log)}")
            for error in self.session.errors_log:
                print(f"   - {error['poet_name']}: {error['error']}")
        
        print("=" * 60 + "\n")


# ============================================================================
# Convenience functions for common workflows
# ============================================================================

def run_mushaira_simple(
    theme: str,
    storage_dir: str = "./data",
    verbose: bool = True,
) -> MushairaSession:
    """
    Quick start: run a complete mushaira and generate outputs.
    
    Args:
        theme: The mushaira theme (e.g., "ishq aur judai")
        storage_dir: Where to store outputs
        verbose: Print progress
    
    Returns:
        Completed MushairaSession
    """
    orchestrator = MushairaOrchestrator(
        theme=theme,
        storage_dir=storage_dir,
        enable_checkpoints=True,
    )
    
    # Optional callbacks for progress
    if verbose:
        orchestrator.on_poet_start = lambda pos, name: print(f"Starting {name}...")
        orchestrator.on_poet_complete = lambda pos, name, verse: print(f"✓ {name} complete")
        orchestrator.on_error = lambda pos, name, err: print(f"✗ {name} error: {err}")
    
    # Run
    session = orchestrator.run()
    
    # Generate outputs
    if session.is_complete():
        orchestrator.generate_outputs()
        orchestrator.print_summary()
    
    return session


def resume_mushaira(
    session_id: str,
    storage_dir: str = "./data",
) -> MushairaSession:
    """
    Resume a mushaira that was interrupted.
    Loads from checkpoint and continues from last successful poet.
    
    Args:
        session_id: UUID of the session to resume
        storage_dir: Storage directory
    
    Returns:
        Resumed/completed MushairaSession
    """
    config = StorageConfig(base_dir=storage_dir)
    checkpoint_manager = CheckpointManager(config)
    
    # Try checkpoint first, then regular session
    session = checkpoint_manager.load_checkpoint(session_id)
    if not session:
        session_store = SessionStore(config)
        session = session_store.load_session(session_id)
    
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    print(f"📖 Resuming session: {session_id}")
    print(f"   Last completed poet: {len(session.poet_outputs)}/7")
    
    # TODO: Continue from position len(session.poet_outputs) + 1
    # For now, this is a placeholder
    
    return session
