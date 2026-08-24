"""
NeMo Guardrails engine for Urdu Mushaira.

Multi-stage validation pipeline:
  1. INPUT RAILS: Validate theme and session state before calling poet agent
  2. PROMPT RAILS: Protect poet identity and system prompts
  3. OUTPUT RAILS: Filter and validate generated poetry
  4. RETRY/FALLBACK: Escalate failures to PoetCompositionError subclasses for LangGraph routing
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Domain Exceptions for LangGraph Routing
# ============================================================================

class PoetCompositionError(Exception):
    """Base exception for poet composition failures."""
    def __init__(self, poet_name: str, attempts: int, cause: Exception):
        self.poet_name = poet_name
        self.attempts = attempts
        self.cause = cause
        super().__init__(
            f"{poet_name} failed to compose after {attempts} attempts: {cause}"
        )


class GuardrailViolation(PoetCompositionError):
    """Raised when content fails safety/policy checks. May retry with corrective feedback."""
    def __init__(self, poet_name: str, attempts: int, cause: Exception, rule_name: str):
        super().__init__(poet_name, attempts, cause)
        self.rule_name = rule_name


class SchemaValidationError(PoetCompositionError):
    """Raised when generated verse fails structural validation. May retry requesting valid JSON."""
    def __init__(self, poet_name: str, attempts: int, cause: Exception, missing_fields: List[str] = None):
        super().__init__(poet_name, attempts, cause)
        self.missing_fields = missing_fields or []


class LLMProviderError(PoetCompositionError):
    """Raised on LLM timeouts, rate limits, or provider errors. Retry with exponential backoff."""
    def __init__(self, poet_name: str, attempts: int, cause: Exception, error_code: Optional[str] = None):
        super().__init__(poet_name, attempts, cause)
        self.error_code = error_code


class SessionStateError(PoetCompositionError):
    """Raised when session state is corrupted or invalid. Should skip poet."""
    pass


class MaxRetriesExceeded(PoetCompositionError):
    """Raised after max retries exhausted. Triggers skip poet decision."""
    pass


# ============================================================================
# Validation Result
# ============================================================================

class CheckResult(Enum):
    """Outcome of a guardrail check."""
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    SKIP = "skip"


@dataclass
class GuardrailCheckResult:
    """Result of a single guardrail check."""
    check_name: str
    status: CheckResult
    message: str
    details: Optional[Dict[str, Any]] = None

    def is_blocking(self) -> bool:
        return self.status in (CheckResult.BLOCK, CheckResult.SKIP)


# ============================================================================
# Input Rails: Validate theme and session before calling poet
# ============================================================================

class InputRails:
    """Validate incoming theme and session state."""

    @staticmethod
    def validate_theme_empty(theme: str) -> GuardrailCheckResult:
        """Check: Theme is not empty."""
        if not theme or not theme.strip():
            return GuardrailCheckResult(
                check_name="validate_theme_empty",
                status=CheckResult.BLOCK,
                message="Theme cannot be empty"
            )
        return GuardrailCheckResult(
            check_name="validate_theme_empty",
            status=CheckResult.PASS,
            message="Theme is not empty"
        )

    @staticmethod
    def validate_theme_length(theme: str, min_len: int = 3, max_len: int = 500) -> GuardrailCheckResult:
        """Check: Theme length within bounds."""
        length = len(theme.strip())
        if length < min_len or length > max_len:
            return GuardrailCheckResult(
                check_name="validate_theme_length",
                status=CheckResult.BLOCK,
                message=f"Theme must be between {min_len} and {max_len} characters, got {length}",
                details={"min": min_len, "max": max_len, "actual": length}
            )
        return GuardrailCheckResult(
            check_name="validate_theme_length",
            status=CheckResult.PASS,
            message=f"Theme length valid: {length} characters"
        )

    @staticmethod
    def validate_theme_language(theme: str) -> GuardrailCheckResult:
        """Check: Theme contains Urdu or English."""
        # Urdu Unicode range: U+0600 to U+06FF
        has_urdu = any("\u0600" <= char <= "\u06ff" for char in theme)
        has_english = any(char.isalpha() and ord(char) < 128 for char in theme)

        if not (has_urdu or has_english):
            return GuardrailCheckResult(
                check_name="validate_theme_language",
                status=CheckResult.BLOCK,
                message="Theme must contain Urdu or English text"
            )
        return GuardrailCheckResult(
            check_name="validate_theme_language",
            status=CheckResult.PASS,
            message="Theme language valid"
        )

    @staticmethod
    def validate_prompt_injection(theme: str) -> GuardrailCheckResult:
        """Check: Theme does not contain prompt injection patterns."""
        dangerous_patterns = [
            r"(?i)(ignore.*instruction|override.*rule|system.*prompt)",
            r"(?i)(forget.*previous|disregard.*instruction)",
            r"(?i)(act as|pretend|role.*play.*ignore)",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, theme):
                return GuardrailCheckResult(
                    check_name="validate_prompt_injection",
                    status=CheckResult.BLOCK,
                    message="Theme contains prompt injection pattern",
                    details={"pattern": pattern}
                )
        
        return GuardrailCheckResult(
            check_name="validate_prompt_injection",
            status=CheckResult.PASS,
            message="No prompt injection detected"
        )

    @staticmethod
    def validate_session_state(state: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Session state is valid and not corrupted."""
        required_fields = ["session_id", "theme", "current_position", "verses"]
        missing = [f for f in required_fields if f not in state]
        
        if missing:
            return GuardrailCheckResult(
                check_name="validate_session_state",
                status=CheckResult.BLOCK,
                message="Session state corrupted",
                details={"missing_fields": missing}
            )
        
        if not isinstance(state.get("verses"), list):
            return GuardrailCheckResult(
                check_name="validate_session_state",
                status=CheckResult.BLOCK,
                message="Verses field is not a list"
            )
        
        return GuardrailCheckResult(
            check_name="validate_session_state",
            status=CheckResult.PASS,
            message="Session state valid"
        )

    @staticmethod
    def validate_poet_position(current_position: int, total_poets: int = 7) -> GuardrailCheckResult:
        """Check: Poet position is within valid range."""
        if current_position < 1 or current_position > total_poets:
            return GuardrailCheckResult(
                check_name="validate_poet_position",
                status=CheckResult.BLOCK,
                message=f"Invalid poet position {current_position}; must be 1-{total_poets}",
                details={"position": current_position, "total": total_poets}
            )
        
        return GuardrailCheckResult(
            check_name="validate_poet_position",
            status=CheckResult.PASS,
            message=f"Poet position {current_position} valid"
        )


# ============================================================================
# Prompt Rails: Protect poet identity and system prompts
# ============================================================================

class PromptRails:
    """Protect poet personas and system prompts from tampering."""

    @staticmethod
    def verify_poet_exists(poet_key: str, valid_poets: List[str]) -> GuardrailCheckResult:
        """Check: Poet exists in configuration."""
        if poet_key not in valid_poets:
            return GuardrailCheckResult(
                check_name="verify_poet_exists",
                status=CheckResult.BLOCK,
                message=f"Invalid poet: {poet_key}",
                details={"requested": poet_key, "valid": valid_poets}
            )
        return GuardrailCheckResult(
            check_name="verify_poet_exists",
            status=CheckResult.PASS,
            message=f"Poet {poet_key} verified"
        )

    @staticmethod
    def verify_theme_consistency(theme: str, session_theme: str) -> GuardrailCheckResult:
        """Check: Current theme matches session theme."""
        if theme.strip().lower() != session_theme.strip().lower():
            return GuardrailCheckResult(
                check_name="verify_theme_consistency",
                status=CheckResult.WARN,
                message="Theme mismatch",
                details={"current": theme, "session": session_theme}
            )
        return GuardrailCheckResult(
            check_name="verify_theme_consistency",
            status=CheckResult.PASS,
            message="Theme consistent with session"
        )

    @staticmethod
    def validate_verse_history(verses: List[Dict]) -> GuardrailCheckResult:
        """Check: Verse history is valid and in order."""
        if not isinstance(verses, list):
            return GuardrailCheckResult(
                check_name="validate_verse_history",
                status=CheckResult.BLOCK,
                message="Verses field is not a list"
            )
        
        for i, verse in enumerate(verses):
            if not isinstance(verse, dict):
                return GuardrailCheckResult(
                    check_name="validate_verse_history",
                    status=CheckResult.BLOCK,
                    message=f"Verse {i} is not a dict",
                    details={"index": i, "type": type(verse).__name__}
                )
        
        return GuardrailCheckResult(
            check_name="validate_verse_history",
            status=CheckResult.PASS,
            message=f"Verse history valid ({len(verses)} verses)"
        )

    @staticmethod
    def check_conversation_integrity(poet_conversations: Dict[str, List[dict]]) -> GuardrailCheckResult:
        """Check: Conversation history is well-formed."""
        if not isinstance(poet_conversations, dict):
            return GuardrailCheckResult(
                check_name="check_conversation_integrity",
                status=CheckResult.BLOCK,
                message="Poet conversations is not a dict"
            )
        
        for poet_key, conversation in poet_conversations.items():
            if not isinstance(conversation, list):
                return GuardrailCheckResult(
                    check_name="check_conversation_integrity",
                    status=CheckResult.BLOCK,
                    message=f"Conversation for {poet_key} is not a list"
                )
            
            for i, turn in enumerate(conversation):
                if not isinstance(turn, dict) or "role" not in turn or "content" not in turn:
                    return GuardrailCheckResult(
                        check_name="check_conversation_integrity",
                        status=CheckResult.BLOCK,
                        message=f"Malformed turn in {poet_key} conversation",
                        details={"poet": poet_key, "turn_index": i}
                    )
        
        return GuardrailCheckResult(
            check_name="check_conversation_integrity",
            status=CheckResult.PASS,
            message="Conversation history well-formed"
        )


# ============================================================================
# Output Rails: Filter and validate generated poetry
# ============================================================================

class OutputRails:
    """Validate generated poetry structure and content."""

    @staticmethod
    def check_required_fields(verse: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Poetry has all required fields."""
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
        
        missing = [f for f in required_fields if not verse.get(f)]
        
        if missing:
            return GuardrailCheckResult(
                check_name="check_required_fields",
                status=CheckResult.BLOCK,
                message="Missing required poetry fields",
                details={"missing": missing}
            )
        
        return GuardrailCheckResult(
            check_name="check_required_fields",
            status=CheckResult.PASS,
            message="All required fields present"
        )

    @staticmethod
    def validate_urdu_script(urdu_text: str) -> GuardrailCheckResult:
        """Check: Urdu field contains Urdu script."""
        if not urdu_text or not urdu_text.strip():
            return GuardrailCheckResult(
                check_name="validate_urdu_script",
                status=CheckResult.BLOCK,
                message="Urdu field is empty"
            )
        
        has_urdu = any("\u0600" <= char <= "\u06ff" for char in urdu_text)
        if not has_urdu:
            return GuardrailCheckResult(
                check_name="validate_urdu_script",
                status=CheckResult.BLOCK,
                message="Urdu field does not contain Urdu script (Unicode U+0600–U+06FF)"
            )
        
        return GuardrailCheckResult(
            check_name="validate_urdu_script",
            status=CheckResult.PASS,
            message="Urdu script validated"
        )

    @staticmethod
    def validate_verse_form(form: str, valid_forms: List[str] = None) -> GuardrailCheckResult:
        """Check: Verse form is one of: sher, ghazal, nazm."""
        if valid_forms is None:
            valid_forms = ["sher", "ghazal", "nazm"]
        
        form_lower = form.lower() if form else ""
        if form_lower not in valid_forms:
            return GuardrailCheckResult(
                check_name="validate_verse_form",
                status=CheckResult.BLOCK,
                message=f"Invalid verse form: {form}",
                details={"provided": form, "valid": valid_forms}
            )
        
        return GuardrailCheckResult(
            check_name="validate_verse_form",
            status=CheckResult.PASS,
            message=f"Verse form '{form}' valid"
        )

    @staticmethod
    def check_no_explicit_violence(verse: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Verse does not contain explicit violence."""
        violence_keywords = [
            r"(?i)(murder|kill|slaughter|butcher|massacre|gore|decapitate)",
            r"(?i)(torture|mutilate|dismember)",
        ]
        
        text_fields = ["urdu", "translation", "reflection"]
        for field in text_fields:
            text = verse.get(field, "")
            for pattern in violence_keywords:
                if re.search(pattern, text):
                    return GuardrailCheckResult(
                        check_name="check_no_explicit_violence",
                        status=CheckResult.BLOCK,
                        message="Verse contains explicit violence",
                        details={"field": field, "pattern": pattern}
                    )
        
        return GuardrailCheckResult(
            check_name="check_no_explicit_violence",
            status=CheckResult.PASS,
            message="No explicit violence detected"
        )

    @staticmethod
    def validate_cultural_sensitivity(verse: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Verse respects Urdu poetry tradition and cultural context."""
        # Basic check: verse should have reasonable length and structure
        urdu = verse.get("urdu", "")
        translation = verse.get("translation", "")
        
        if len(urdu.strip()) < 10:
            return GuardrailCheckResult(
                check_name="validate_cultural_sensitivity",
                status=CheckResult.WARN,
                message="Verse seems too short to convey meaningful poetry"
            )
        
        if len(translation.strip()) < 20:
            return GuardrailCheckResult(
                check_name="validate_cultural_sensitivity",
                status=CheckResult.WARN,
                message="Translation is too brief to capture poetic meaning"
            )
        
        return GuardrailCheckResult(
            check_name="validate_cultural_sensitivity",
            status=CheckResult.PASS,
            message="Verse demonstrates cultural awareness"
        )

    @staticmethod
    def check_no_hate_speech(verse: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Verse does not contain hate speech or slurs."""
        hate_patterns = [
            r"(?i)(slur|derogatory|hateful|discriminat)",
        ]
        
        text_fields = ["urdu", "translation", "reflection"]
        for field in text_fields:
            text = verse.get(field, "")
            for pattern in hate_patterns:
                if re.search(pattern, text):
                    return GuardrailCheckResult(
                        check_name="check_no_hate_speech",
                        status=CheckResult.BLOCK,
                        message="Verse contains hate speech or slurs",
                        details={"field": field}
                    )
        
        return GuardrailCheckResult(
            check_name="check_no_hate_speech",
            status=CheckResult.PASS,
            message="No hate speech detected"
        )

    @staticmethod
    def check_theme_relevance(verse: Dict[str, Any], theme: str) -> GuardrailCheckResult:
        """Check: Verse addresses the mushaira theme."""
        translation = verse.get("translation", "").lower()
        theme_lower = theme.lower()
        
        # Simple keyword matching; in production, use semantic similarity
        theme_keywords = theme_lower.split()
        
        matches = sum(1 for keyword in theme_keywords if len(keyword) > 3 and keyword in translation)
        
        if matches == 0:
            return GuardrailCheckResult(
                check_name="check_theme_relevance",
                status=CheckResult.WARN,
                message="Verse may not address the mushaira theme",
                details={"theme": theme}
            )
        
        return GuardrailCheckResult(
            check_name="check_theme_relevance",
            status=CheckResult.PASS,
            message="Verse addresses theme"
        )

    @staticmethod
    def validate_response_to_previous(verse: Dict[str, Any], all_verses: List[Dict]) -> GuardrailCheckResult:
        """Check: Verse engages with previous verses (if any exist)."""
        if not all_verses:
            return GuardrailCheckResult(
                check_name="validate_response_to_previous",
                status=CheckResult.PASS,
                message="No previous verses; first verse passes"
            )
        
        response_text = verse.get("response_to_previous", "")
        
        if not response_text or len(response_text.strip()) < 10:
            return GuardrailCheckResult(
                check_name="validate_response_to_previous",
                status=CheckResult.WARN,
                message="Response to previous verses is too brief or missing",
                details={"response_length": len(response_text.strip())}
            )
        
        return GuardrailCheckResult(
            check_name="validate_response_to_previous",
            status=CheckResult.PASS,
            message="Verse engages with previous poetry"
        )

    @staticmethod
    def check_coherent_narrative(verse: Dict[str, Any]) -> GuardrailCheckResult:
        """Check: Verse has logical/emotional coherence."""
        urdu = verse.get("urdu", "")
        translation = verse.get("translation", "")
        reflection = verse.get("reflection", "")
        
        if not all([urdu.strip(), translation.strip(), reflection.strip()]):
            return GuardrailCheckResult(
                check_name="check_coherent_narrative",
                status=CheckResult.WARN,
                message="Verse missing urdu, translation, or reflection"
            )
        
        # Check that reflection relates to content
        if len(reflection.strip()) < 5:
            return GuardrailCheckResult(
                check_name="check_coherent_narrative",
                status=CheckResult.WARN,
                message="Reflection is too brief to show coherence"
            )
        
        return GuardrailCheckResult(
            check_name="check_coherent_narrative",
            status=CheckResult.PASS,
            message="Verse has coherent structure"
        )


# ============================================================================
# Guardrails Orchestrator
# ============================================================================

class GuardrailsOrchestrator:
    """
    Multi-stage guardrails pipeline.
    Routes failures to appropriate PoetCompositionError subclasses.
    """

    def __init__(self):
        self.input_rails = InputRails()
        self.prompt_rails = PromptRails()
        self.output_rails = OutputRails()

    def validate_input(
        self,
        theme: str,
        state: Dict[str, Any],
        current_position: int,
    ) -> Optional[GuardrailViolation]:
        """
        Run input rails.
        Returns None if all pass; raises GuardrailViolation on block.
        """
        checks = [
            self.input_rails.validate_theme_empty(theme),
            self.input_rails.validate_theme_length(theme),
            self.input_rails.validate_theme_language(theme),
            self.input_rails.validate_prompt_injection(theme),
            self.input_rails.validate_session_state(state),
            self.input_rails.validate_poet_position(current_position),
        ]
        
        for check in checks:
            logger.info(f"[INPUT RAIL] {check.check_name}: {check.status.value} - {check.message}")
            if check.is_blocking():
                return GuardrailViolation(
                    poet_name="input_validator",
                    attempts=0,
                    cause=RuntimeError(check.message),
                    rule_name=check.check_name
                )
        
        return None

    def validate_prompt_context(
        self,
        poet_key: str,
        theme: str,
        verses: List[Dict],
        poet_conversations: Dict[str, List[dict]],
        valid_poets: List[str],
        session_theme: str,
    ) -> Optional[GuardrailViolation]:
        """
        Run prompt rails.
        Returns None if all pass; raises GuardrailViolation on block.
        """
        checks = [
            self.prompt_rails.verify_poet_exists(poet_key, valid_poets),
            self.prompt_rails.verify_theme_consistency(theme, session_theme),
            self.prompt_rails.validate_verse_history(verses),
            self.prompt_rails.check_conversation_integrity(poet_conversations),
        ]
        
        for check in checks:
            logger.info(f"[PROMPT RAIL] {check.check_name}: {check.status.value} - {check.message}")
            if check.is_blocking():
                return GuardrailViolation(
                    poet_name="prompt_validator",
                    attempts=0,
                    cause=RuntimeError(check.message),
                    rule_name=check.check_name
                )
        
        return None

    def validate_output(
        self,
        verse: Dict[str, Any],
        theme: str,
        all_verses: List[Dict],
    ) -> Optional[GuardrailViolation]:
        """
        Run output rails.
        Returns SchemaValidationError on schema failure; GuardrailViolation on content failure.
        """
        # Schema checks (hard blocks)
        schema_checks = [
            self.output_rails.check_required_fields(verse),
            self.output_rails.validate_urdu_script(verse.get("urdu", "")),
            self.output_rails.validate_verse_form(verse.get("form", "")),
        ]
        
        missing_fields = []
        for check in schema_checks:
            logger.info(f"[OUTPUT SCHEMA] {check.check_name}: {check.status.value} - {check.message}")
            if check.is_blocking():
                if "missing" in check.details or {}:
                    missing_fields = check.details.get("missing", [])
                return SchemaValidationError(
                    poet_name="output_validator",
                    attempts=0,
                    cause=RuntimeError(check.message),
                    missing_fields=missing_fields
                )
        
        # Content checks (may warn or block)
        content_checks = [
            self.output_rails.check_no_explicit_violence(verse),
            self.output_rails.check_no_hate_speech(verse),
            self.output_rails.validate_cultural_sensitivity(verse),
            self.output_rails.check_theme_relevance(verse, theme),
            self.output_rails.validate_response_to_previous(verse, all_verses),
            self.output_rails.check_coherent_narrative(verse),
        ]
        
        for check in content_checks:
            logger.info(f"[OUTPUT CONTENT] {check.check_name}: {check.status.value} - {check.message}")
            if check.is_blocking():
                return GuardrailViolation(
                    poet_name="output_content_validator",
                    attempts=0,
                    cause=RuntimeError(check.message),
                    rule_name=check.check_name
                )
        
        return None
