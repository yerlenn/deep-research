from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class PlanFeedbackRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ResearchPlan(BaseModel):
    title: str
    goal: str
    steps: list[str]
    expected_output: str


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ResearchRunSummary(BaseModel):
    id: UUID
    status: str
    plan: dict[str, Any] | None = None
    plan_history: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: int | None = None
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    research_run: ResearchRunSummary | None = None


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]
    pending_runs: list[ResearchRunSummary]


class CreateRunResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    run_id: UUID
    plan: dict[str, Any]


class EventResponse(BaseModel):
    id: UUID
    sequence_number: int
    event_type: str
    title: str
    content: str
    url: str | None = None
    metadata: dict[str, Any]
    created_at: datetime


class PlanFeedbackResponse(BaseModel):
    run_id: UUID
    plan: dict[str, Any]


class ApproveRunResponse(BaseModel):
    run_id: UUID
    status: str
    duration_seconds: int | None = None
