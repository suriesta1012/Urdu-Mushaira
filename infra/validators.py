"""Request and response validators for API endpoints."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class MushairaRequestSchema(BaseModel):
    """Validated request for starting a mushaira session."""
    
    theme: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Theme or prompt for the mushaira",
        example="ishq aur judai (love and separation)"
    )
    
    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate theme is not just whitespace."""
        if not v.strip():
            raise ValueError("Theme cannot be empty or whitespace")
        return v.strip()


class VerseResponse(BaseModel):
    """A single verse in the mushaira."""
    
    poet_name: str
    poet_urdu_name: str
    form: str  # sher, ghazal, nazm
    urdu: str
    transliteration: str
    translation: str
    reflection: str
    response_to_previous: Optional[str] = None
    next_prompt: str


class MushairaStatusResponse(BaseModel):
    """Status response for an active or completed mushaira."""
    
    session_id: str
    theme: str
    verses: list[VerseResponse]
    status: str  # running, completed, failed
    failed_poets: list[str]
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""
    
    status: str = "ok"
    version: str = "0.2.0"
    postgres_connected: Optional[bool] = None
    langfuse_connected: Optional[bool] = None
