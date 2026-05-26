import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class RunStatus(str, Enum):
    planning = "planning"
    awaiting_approval = "awaiting_approval"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    research_runs: Mapped[list["ResearchRun"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(40), default=RunStatus.awaiting_approval.value)
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    plan_history: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    search_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="research_runs")
    events: Mapped[list["ResearchEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    report: Mapped["ResearchReport | None"] = relationship(back_populates="run", cascade="all, delete-orphan")
    subtasks: Mapped[list["ResearchSubtask"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ResearchPlanFeedback(Base):
    __tablename__ = "research_plan_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)
    generated_plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRun] = relationship(back_populates="events")


class ResearchSubtask(Base):
    __tablename__ = "research_subtasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    sequence_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRun] = relationship(back_populates="subtasks")
    sources: Mapped[list["ResearchSource"]] = relationship(back_populates="subtask", cascade="all, delete-orphan")
    findings: Mapped[list["ResearchFinding"]] = relationship(back_populates="subtask", cascade="all, delete-orphan")


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    subtask_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_subtasks.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subtask: Mapped[ResearchSubtask] = relationship(back_populates="sources")


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), index=True)
    subtask_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_subtasks.id", ondelete="CASCADE"), index=True)
    claim: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    source_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    confidence: Mapped[str] = mapped_column(String(40), default="medium")
    gaps: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subtask: Mapped[ResearchSubtask] = relationship(back_populates="findings")


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"), unique=True)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRun] = relationship(back_populates="report")
