"""
BasePoetAgent — the foundation every poet agent inherits from.

This is the bridge between poet_config.py (who the poet IS)
and the actual Anthropic API call (what the poet SAYS).
Each subclass in poet_agents.py only needs to define:
  - system_prompt()   → their unique voice/persona
  - compose_poetry()  → inherited, calls Claude via API
"""

import os
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from anthropic import Anthropic

from agents.poet_config import PoetProfile

client = Anthropic()  # reads ANTHROPIC_API_KEY from env


@dataclass
class PoetryData:
    """Structured output from a single poet's recitation."""
    form: str                      # sher / ghazal / nazm
    urdu: str                      # verse in Urdu script
    transliteration: str           # Roman Urdu
    translation: str               # English meaning
    reflection: str                # one sentence on mood/imagery
    next_prompt: str               # thematic baton to next poet
    poet_name: str = ""
    poet_urdu_name: str = ""
    retrieved_context: List[str] = field(default_factory=list)   # which shers were retrieved


@dataclass
class PoetryData:
    """Structured output from a single poet's recitation."""
    form: str
    urdu: str
    transliteration: str
    translation: str
    reflection: str
    next_prompt: str
    poet_name: str = ""
    poet_urdu_name: str = ""
    retrieved_context: List[str] = field(default_factory=list)


class BasePoetAgent:
    """
    Abstract base for all poet agents.

    Subclasses must implement:
        system_prompt(self) -> str

    They inherit compose_poetry() which handles:
        1. RAG retrieval (if retriever is attached)
        2. Anthropic API call with full context
        3. JSON parsing and PoetryData construction
        4. Retry logic
    """

    def __init__(self, poet_profile: PoetProfile, position: int):
        self.poet_profile = poet_profile
        self.position = position
        self.retriever = None          # injected by orchestrator if RAG is enabled
        self._conversation: List[Dict] = []

    # ------------------------------------------------------------------ #
    # Override in each subclass                                            #
    # ------------------------------------------------------------------ #

    def system_prompt(self) -> str:
        """
        Return a rich, first-person system prompt that puts Claude
        inside the poet's identity, era, vocabulary, and emotional register.
        Subclasses should call super() and append their own content.
        """
        p = self.poet_profile
        return f"""You are {p.name} ({p.urdu_name}), the legendary Urdu poet who lived from {p.birth_year} to {p.death_year}.

Historical period: {p.historical_period}
Specialty: {p.specialty}
Signature themes: {', '.join(p.signature_themes)}
Key works: {', '.join(p.key_works)}

{p.biographical_summary}

You are NOT playing this poet — you ARE this poet, speaking from within your own era and consciousness.
You compose authentic Urdu poetry in your unique voice.

ABSOLUTE RULES:
- The "urdu" field must be real Urdu Unicode script (not transliteration)
- Never reproduce verbatim published verses — compose ORIGINAL work in your style
- Stay in voice — your language, imagery, and emotional register must be unmistakably yours
- Do not acknowledge being an AI or reference the modern world anachronistically
- Respond ONLY with valid JSON matching this exact schema:

{{
  "form": "sher | ghazal | nazm",
  "urdu": "<verse in Urdu script>",
  "transliteration": "<Roman Urdu, line by line>",
  "translation": "<English meaning>",
  "reflection": "<one sentence on mood or imagery used>",
  "next_prompt": "<a theme or image to pass to the next poet>"
}}
"""

    # ------------------------------------------------------------------ #
    # Core composition — do not override                                   #
    # ------------------------------------------------------------------ #

    def compose_poetry(
        self,
        theme: str,
        previous_sher: Optional[str] = None,
        max_retries: int = 3,
    ) -> PoetryData:
        """
        Main entry point. Called by the orchestrator for each poet's turn.

        Args:
            theme: The mushaira theme (e.g. "ishq aur judai")
            previous_sher: The last poet's verse (Urdu + transliteration)
            max_retries: How many times to retry on parse failure

        Returns:
            PoetryData with all fields populated
        """
        # 1. RAG retrieval
        retrieved = []
        if self.retriever is not None:
            retrieved = self.retriever.get_context(
                poet_id=self._poet_id(),
                query=theme,
                k=4,
            )

        # 2. Build the user message
        user_message = self._build_user_message(theme, previous_sher, retrieved)

        # 3. Call Claude with retries
        for attempt in range(max_retries):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    system=self.system_prompt(),
                    messages=[{"role": "user", "content": user_message}],
                )
                raw = response.content[0].text.strip()
                data = self._parse_response(raw)
                data.poet_name = self.poet_profile.name
                data.poet_urdu_name = self.poet_profile.urdu_name
                data.retrieved_context = retrieved
                return data

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"{self.poet_profile.name} failed to compose after {max_retries} attempts: {e}"
                    )
                time.sleep(2 ** attempt)  # exponential backoff

    def _build_user_message(
        self,
        theme: str,
        previous_sher: Optional[str],
        retrieved: List[str],
    ) -> str:
        parts = []

        # RAG context block
        if retrieved:
            parts.append("Here are some of your own verses on related themes — use these as inspiration for your imagery and vocabulary, but compose something new:\n")
            for i, sher in enumerate(retrieved, 1):
                parts.append(f"  [{i}] {sher}")
            parts.append("")

        # Previous poet's verse
        if previous_sher:
            parts.append(f"The previous poet has just recited:\n\n{previous_sher}\n")
            parts.append("Now it is your turn. You may respond to their theme, continue their mood, or contrast it — but speak in your own voice.\n")
        else:
            parts.append("You are the first to recite in this mushaira. Set the tone.\n")

        parts.append(f"Theme of this mushaira: \"{theme}\"")
        parts.append("\nCompose your verse. Output ONLY the JSON schema specified.")

        return "\n".join(parts)

    def _parse_response(self, raw: str) -> PoetryData:
        """Parse Claude's JSON response into PoetryData."""
        # Strip markdown fences if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        return PoetryData(
            form=data.get("form", "sher"),
            urdu=data["urdu"],
            transliteration=data["transliteration"],
            translation=data["translation"],
            reflection=data.get("reflection", ""),
            next_prompt=data.get("next_prompt", ""),
        )

    def _poet_id(self) -> str:
        """Stable key for RAG namespace lookup."""
        return self.poet_profile.name.lower().replace(" ", "_")

    def create_reflection(self, state: Dict) -> str:
        """Optional: called after full mushaira for a meta-reflection."""
        return f"{self.poet_profile.name}: honored to have recited in this mehfil."
