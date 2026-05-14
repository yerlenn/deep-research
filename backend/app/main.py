from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user
from .config import get_settings
from .database import Base, engine, get_db
from .mock_agent import build_events, build_plan, build_report, build_research_intro, title_from_prompt
from .models import Conversation, Message, MessageRole, ResearchEvent, ResearchPlanFeedback, ResearchReport, ResearchRun, RunStatus
from .schemas import (
    ApproveRunResponse,
    ConversationResponse,
    ConversationSummary,
    CreateRunResponse,
    EventResponse,
    MessageRequest,
    MessageResponse,
    PlanFeedbackRequest,
    PlanFeedbackResponse,
    PromptRequest,
    ResearchRunSummary,
)


settings = get_settings()
app = FastAPI(title="Deep Research Starter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


Db = Annotated[Session, Depends(get_db)]
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def ensure_conversation(db: Session, user_id: UUID, conversation_id: UUID) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def ensure_run(db: Session, user_id: UUID, run_id: UUID) -> ResearchRun:
    run = db.scalar(
        select(ResearchRun)
        .join(Conversation, Conversation.id == ResearchRun.conversation_id)
        .where(ResearchRun.id == run_id, Conversation.user_id == user_id)
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research run not found")
    return run


def run_summary(run: ResearchRun) -> ResearchRunSummary:
    return ResearchRunSummary(
        id=run.id,
        status=run.status,
        plan=run.plan,
        duration_seconds=run.duration_seconds,
        created_at=run.created_at,
    )


def conversation_response(db: Session, conversation: Conversation) -> ConversationResponse:
    runs = db.scalars(select(ResearchRun).where(ResearchRun.conversation_id == conversation.id)).all()
    runs_by_id = {run.id: run for run in runs}
    pending_runs = [
        run_summary(run)
        for run in runs
        if run.status in {RunStatus.awaiting_approval.value, RunStatus.planning.value, RunStatus.running.value}
        and not any(message.research_run_id == run.id for message in conversation.messages)
    ]
    messages = [
        MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            research_run=run_summary(runs_by_id[message.research_run_id]) if message.research_run_id in runs_by_id else None,
        )
        for message in sorted(conversation.messages, key=lambda item: item.created_at)
    ]
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
        pending_runs=pending_runs,
    )


def create_planned_run(db: Session, user_id: UUID, prompt: str, conversation: Conversation | None = None) -> tuple[Conversation, Message, ResearchRun]:
    if conversation is None:
        conversation = Conversation(user_id=user_id, title=title_from_prompt(prompt))
        db.add(conversation)
        db.flush()

    user_message = Message(conversation_id=conversation.id, role=MessageRole.user.value, content=prompt)
    db.add(user_message)
    db.flush()

    run = ResearchRun(
        conversation_id=conversation.id,
        trigger_message_id=user_message.id,
        status=RunStatus.awaiting_approval.value,
        plan=build_plan(prompt),
    )
    db.add(run)
    db.commit()
    db.refresh(conversation)
    db.refresh(user_message)
    db.refresh(run)
    return conversation, user_message, run


@app.post("/api/research-runs", response_model=CreateRunResponse)
def create_research_run(payload: PromptRequest, db: Db, current: AuthUser) -> CreateRunResponse:
    conversation, message, run = create_planned_run(db, current.user.id, payload.prompt)
    return CreateRunResponse(conversation_id=conversation.id, message_id=message.id, run_id=run.id, plan=run.plan)


@app.post("/api/conversations/{conversation_id}/messages", response_model=CreateRunResponse)
def create_followup(conversation_id: UUID, payload: MessageRequest, db: Db, current: AuthUser) -> CreateRunResponse:
    conversation = ensure_conversation(db, current.user.id, conversation_id)
    conversation, message, run = create_planned_run(db, current.user.id, payload.content, conversation)
    return CreateRunResponse(conversation_id=conversation.id, message_id=message.id, run_id=run.id, plan=run.plan)


@app.post("/api/research-runs/{run_id}/plan-feedback", response_model=PlanFeedbackResponse)
def revise_plan(run_id: UUID, payload: PlanFeedbackRequest, db: Db, current: AuthUser) -> PlanFeedbackResponse:
    run = ensure_run(db, current.user.id, run_id)
    if run.status not in {RunStatus.awaiting_approval.value, RunStatus.planning.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only unapproved plans can be revised")
    trigger_message = db.get(Message, run.trigger_message_id)
    prompt = trigger_message.content if trigger_message else run.plan.get("goal", "Research request")
    new_plan = build_plan(prompt, payload.message)
    db.add(ResearchPlanFeedback(run_id=run.id, message=payload.message, generated_plan=new_plan))
    run.plan = new_plan
    run.status = RunStatus.awaiting_approval.value
    db.commit()
    db.refresh(run)
    return PlanFeedbackResponse(run_id=run.id, plan=run.plan)


@app.post("/api/research-runs/{run_id}/approve", response_model=ApproveRunResponse)
def approve_run(run_id: UUID, db: Db, current: AuthUser) -> ApproveRunResponse:
    run = ensure_run(db, current.user.id, run_id)
    if run.status == RunStatus.completed.value:
        return ApproveRunResponse(run_id=run.id, status=run.status, duration_seconds=run.duration_seconds or 0)
    if run.status not in {RunStatus.awaiting_approval.value, RunStatus.planning.value}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run cannot be approved from its current state")

    trigger_message = db.get(Message, run.trigger_message_id)
    prompt = trigger_message.content if trigger_message else run.plan.get("goal", "Research request")
    now = datetime.now(timezone.utc)
    duration_seconds = 154
    run.status = RunStatus.completed.value
    run.approved_at = now
    run.started_at = now
    run.completed_at = now
    run.duration_seconds = duration_seconds

    intro = Message(conversation_id=run.conversation_id, role=MessageRole.assistant.value, content=build_research_intro(prompt))
    db.add(intro)
    for event in build_events(prompt):
        db.add(ResearchEvent(run_id=run.id, **event))

    report_text = build_report(prompt)
    report_message = Message(
        conversation_id=run.conversation_id,
        role=MessageRole.assistant.value,
        content=report_text,
        research_run_id=run.id,
    )
    db.add(report_message)
    db.flush()
    db.add(ResearchReport(run_id=run.id, message_id=report_message.id, markdown=report_text))
    db.commit()
    db.refresh(run)
    return ApproveRunResponse(run_id=run.id, status=run.status, duration_seconds=duration_seconds)


@app.get("/api/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Db, current: AuthUser) -> list[ConversationSummary]:
    conversations = db.scalars(
        select(Conversation).where(Conversation.user_id == current.user.id).order_by(Conversation.updated_at.desc())
    ).all()
    return [
        ConversationSummary(id=item.id, title=item.title, created_at=item.created_at, updated_at=item.updated_at)
        for item in conversations
    ]


@app.post("/api/conversations", response_model=ConversationSummary)
def create_empty_conversation(db: Db, current: AuthUser) -> ConversationSummary:
    conversation = Conversation(user_id=current.user.id, title="New research")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationSummary(id=conversation.id, title=conversation.title, created_at=conversation.created_at, updated_at=conversation.updated_at)


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: UUID, db: Db, current: AuthUser) -> ConversationResponse:
    conversation = ensure_conversation(db, current.user.id, conversation_id)
    return conversation_response(db, conversation)


@app.get("/api/research-runs/{run_id}/events", response_model=list[EventResponse])
def get_run_events(run_id: UUID, db: Db, current: AuthUser) -> list[EventResponse]:
    ensure_run(db, current.user.id, run_id)
    events = db.scalars(select(ResearchEvent).where(ResearchEvent.run_id == run_id).order_by(ResearchEvent.sequence_number.asc())).all()
    return [
        EventResponse(
            id=event.id,
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            title=event.title,
            content=event.content,
            url=event.url,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]
