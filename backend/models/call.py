from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CallCreate(BaseModel):
    call_sid: str
    from_number: Optional[str] = None
    to_number: Optional[str] = None


class CallUpdate(BaseModel):
    stream_sid: Optional[str] = None
    elevenlabs_conversation_id: Optional[str] = None
    status: Optional[str] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[list[dict]] = None


class TranscriptChunk(BaseModel):
    speaker: str  # "agent" | "caller"
    text: str
    timestamp_ms: Optional[int] = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    call_sid: str
    stream_sid: Optional[str] = None
    elevenlabs_conversation_id: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    transcript: list[dict] = []
    created_at: datetime
