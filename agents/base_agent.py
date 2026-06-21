"""
BasePoetAgent — the foundation every poet agent inherits from.

This is the bridge between poet_config.py (who the poet IS)
and the actual Anthropic API call (what the poet SAYS).

Key design:
  - Each poet is stateless; conversation history is passed in from the graph state.
  - compose_poetry() receives ALL verses recited so far so the poet
    can engage in genuine literary conversation, not just react to
    the immediately preceding sher.
  - The JSON schema includes a `response_to_previous` field: the poet
    explicitly evaluates / responds to the previous sher before composing.
  - Error handling raises PoetCompositionError (not RuntimeError) so
    the graph's error-recovery edge can catch and route cleanly.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from anthropic import Anthropic

from agents.poet_config import PoetProfile

client = Anthropic()   # reads ANTHROPIC_API_KEY from env


# ------------------------------------------------------------------ #
# Domain exceptions                                                    #
# ------------------------------------------------------------------ #

class PoetCompositionError(Exception):
    """Raised when a poet fails to compose after all retries."""
    def __init__(self, poet_name: str, attempts: int, cause: Exception):
        self.poet_name = poet_name
        self.attempts = attempts
        self.cause = cause
        super().__init__(
            f"{poet_name} failed to compose after {attempts} attempts: {cause}"
        )


# ------------------------------------------------------------------ #
# Data model                                                           #
# ------------------------------------------------------------------ #

@dataclass
class PoetryData:
    """Structured output from a single poet's recitation."""
    form: str                       # sher / ghazal / nazm
    urdu: str                       # verse in Urdu script
    transliteration: str            # Roman Urdu
    translation: str                # English meaning
    reflection: str                 # one sentence on mood/imagery
    next_prompt: str                # thematic baton passed to the next poet
    response_to_previous: str = ""  # explicit literary evaluation of previous sher
    poet_name: str = ""
    poet_urdu_name: str = ""
    retrieved_context: List[str] = field(default_factory=list)


# ------------------------------------------------------------------ #
# Base agent                                                           #
# ------------------------------------------------------------------ #

class BasePoetAgent:
    """
    Abstract base for all poet agents.

    Subclasses must implement:
        system_prompt(self) -> str

    They inherit compose_poetry() which handles:
        1. Building a rich multi-turn conversation history
        2. Anthropic API call with full mushaira arc in context
        3. JSON parsing → PoetryData
        4. Retry logic with exponential backoff
        5. Raising PoetCompositionError on terminal failure
    """

    def __init__(self, poet_profile: PoetProfile, position: int):
        self.poet_profile = poet_profile
        self.position = position
        self.retriever = None           # injected if RAG is enabled

    # ------------------------------------------------------------------ #
    # Override in each subclass                                            #
    # ------------------------------------------------------------------ #

    def system_prompt(self) -> str:
        p = self.poet_profile
        return f"""You are {p.name} ({p.urdu_name}), the legendary Urdu poet who lived from {p.birth_year} to {p.death_year}.

Historical period: {p.historical_period}
Specialty: {p.specialty}
Signature themes: {', '.join(p.signature_themes)}
Key works: {', '.join(p.key_works)}

{p.biographical_summary}

You are NOT playing this poet — you ARE this poet, speaking from within your own era and consciousness.
You are participating in a mushaira (a formal Urdu poetry gathering).
This is a living literary conversation: listen deeply to every sher recited before yours,
respond to the emotional and thematic arc they have built, then advance it in your own voice.

ABSOLUTE RULES:
- The "urdu" field must be real Urdu Unicode script (not transliteration)
- Never reproduce verbatim published verses — compose ORIGINAL work in your style
- Stay in voice — your language, imagery, and emotional register must be unmistakably yours
- Do not acknowledge being an AI or reference the modern world anachronistically
- The `response_to_previous` field is your spoken response as a poet — brief appreciation,
  disagreement, or thematic continuation directed at the previous poet. Be genuine.
  If you are first, set this to an empty string.
- Respond ONLY with valid JSON matching this exact schema:

{{
  "response_to_previous": "<your spoken reaction to the previous sher, 1-2 sentences, in English>",
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
        all_verses: List[Dict],   # full list of PoetryData dicts so far
        conversation_history: List[Dict], # messages from graph state
        max_retries: int = 3,
    ) -> Tuple[PoetryData, str, str]:
        """
        Main entry point. Called by the graph node for each poet's turn.

        Args:
            theme:       The mushaira theme (e.g. "ishq aur judai")
            all_verses:  Every verse recited so far (full mushaira arc)
            conversation_history: Prior turns for THIS poet
            max_retries: Retries on JSON parse failure

        Returns:
            Tuple of (PoetryData, raw_json_response, user_message)

        Raises:
            PoetCompositionError on terminal failure (graph can route on this)
        """
        # RAG retrieval (no-op if retriever not injected)
        retrieved = []
        if self.retriever is not None:
            retrieved = self.retriever.get_context(
                poet_id=self._poet_id(),
                query=theme,
                k=4,
            )

        user_message = self._build_user_message(theme, all_verses, retrieved)

        # Build messages for the API call
        messages = conversation_history + [{"role": "user", "content": user_message}]

        last_exc: Exception = Exception("unknown")
        for attempt in range(max_retries):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1200,
                    system=self.system_prompt(),
                    messages=messages,
                )
                raw = response.content[0].text.strip()
                data = self._parse_response(raw)
                data.poet_name = self.poet_profile.name
                data.poet_urdu_name = self.poet_profile.urdu_name
                data.retrieved_context = retrieved

                return data, raw, user_message

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                last_exc = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s backoff

        raise PoetCompositionError(self.poet_profile.name, max_retries, last_exc)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _build_user_message(
        self,
        theme: str,
        all_verses: List[Dict],
        retrieved: List[str],
    ) -> str:
        parts: List[str] = []

        # RAG context block
        if retrieved:
            parts.append(
                "Here are some of your own verses on related themes — "
                "use these as inspiration for imagery and vocabulary, but compose something new:\n"
            )
            for i, sher in enumerate(retrieved, 1):
                parts.append(f"  [{i}] {sher}")
            parts.append("")

        parts.append(f'Theme of this mushaira: "{theme}"\n')

        if not all_verses:
            parts.append(
                "You are the first to recite in this mushaira. "
                "Set the emotional tone for the evening. "
                "There is no previous sher to respond to — open the mehfil.\n"
            )
        else:
            parts.append(
                "The following shers have been recited tonight, in order. "
                "You have heard every one of them. "
                "Read them as a poet listens — not just to the last voice, "
                "but to the whole arc of the evening:\n"
            )
            for v in all_verses:
                poet_label = v.get("poet_name", "Unknown")
                urdu_line  = v.get("urdu", "")
                trans_line = v.get("transliteration", "")
                eng_line   = v.get("translation", "")
                parts.append(f"  ── {poet_label} ──")
                parts.append(f"  {urdu_line}")
                parts.append(f"  {trans_line}")
                parts.append(f"  ({eng_line})\n")

            last = all_verses[-1]
            parts.append(
                f"The last sher was by {last.get('poet_name', 'the previous poet')}. "
                "In `response_to_previous`, speak directly to what they said — "
                "appreciate, challenge, deepen, or pivot. Then compose your own sher.\n"
            )

        parts.append("Output ONLY the JSON schema specified in your instructions.")
        return "\n".join(parts)

    def _parse_response(self, raw: str) -> PoetryData:
        """Parse Claude's JSON response into PoetryData."""
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        return PoetryData(
            form=data.get("form", "sher"),
            urdu=data["urdu"],
            transliteration=data["transliteration"],
            translation=data["translation"],
            reflection=data.get("reflection", ""),
            next_prompt=data.get("next_prompt", ""),
            response_to_previous=data.get("response_to_previous", ""),
        )

    def _poet_id(self) -> str:
        return self.poet_profile.name.lower().replace(" ", "_")
