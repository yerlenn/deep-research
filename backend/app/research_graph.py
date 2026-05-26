from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .agent_services import critique_report, domain_from_url, extract_sources, research_subtask, search_web, synthesize_report
from .agent_types import AgentState
from .config import Settings
from .models import (
    Message,
    MessageRole,
    ResearchEvent,
    ResearchFinding,
    ResearchReport,
    ResearchRun,
    ResearchSource,
    ResearchSubtask,
    RunStatus,
)


def next_sequence(db: Session, run_id: UUID) -> int:
    current = db.scalar(select(func.max(ResearchEvent.sequence_number)).where(ResearchEvent.run_id == run_id))
    return int(current or 0) + 1


def add_event(
    db: Session,
    run_id: UUID,
    event_type: str,
    title: str,
    content: str,
    url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        ResearchEvent(
            run_id=run_id,
            sequence_number=next_sequence(db, run_id),
            event_type=event_type,
            title=title,
            content=content,
            url=url,
            event_metadata=metadata or {},
        )
    )
    db.commit()


class ResearchGraphRunner:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        graph = StateGraph(AgentState)
        graph.add_node("load_run_context", self.load_run_context)
        graph.add_node("create_subtasks", self.create_subtasks)
        graph.add_node("run_subagents", self.run_subagents)
        graph.add_node("synthesize_report", self.synthesize)
        graph.add_node("critique_report", self.critique)
        graph.add_node("save_report", self.save_report)
        graph.add_edge("load_run_context", "create_subtasks")
        graph.add_edge("create_subtasks", "run_subagents")
        graph.add_edge("run_subagents", "synthesize_report")
        graph.add_edge("synthesize_report", "critique_report")
        graph.add_edge("critique_report", "save_report")
        graph.add_edge("save_report", END)
        graph.set_entry_point("load_run_context")
        self.graph = graph.compile()

    def run(self, run_id: UUID) -> None:
        self.graph.invoke({"run_id": str(run_id)}, config={"configurable": {"thread_id": str(run_id)}})

    def _run(self, state: AgentState) -> ResearchRun:
        run = self.db.get(ResearchRun, UUID(state["run_id"]))
        if run is None:
            raise RuntimeError("Research run not found")
        return run

    def load_run_context(self, state: AgentState) -> AgentState:
        run = self._run(state)
        trigger_message = self.db.get(Message, run.trigger_message_id)
        if trigger_message is None:
            raise RuntimeError("Research run trigger message not found")
        run.status = RunStatus.running.value
        run.started_at = datetime.now(timezone.utc)
        run.model_name = self.settings.openai_model
        run.search_provider = "tavily"
        self.db.commit()
        add_event(self.db, run.id, "run_started", "Research started", "The worker loaded the approved plan and started orchestration.")
        intro = Message(
            conversation_id=run.conversation_id,
            role=MessageRole.assistant.value,
            content="I'm researching this now. I'll check reliable sources, compare the evidence, and come back with a concise report.",
        )
        self.db.add(intro)
        self.db.commit()
        return {
            **state,
            "conversation_id": str(run.conversation_id),
            "user_prompt": trigger_message.content,
            "approved_plan": run.plan,
            "subtasks": [],
            "findings": [],
            "sources": [],
            "errors": [],
        }

    def create_subtasks(self, state: AgentState) -> AgentState:
        run = self._run(state)
        plan = state["approved_plan"]
        raw_subtopics = plan.get("subtopics") or []
        if not raw_subtopics:
            raw_subtopics = [
                {"title": step[:120], "objective": step, "search_queries": [state["user_prompt"]]}
                for step in plan.get("steps", [])[: self.settings.max_subagents_per_run]
            ]
        subtasks = raw_subtopics[: self.settings.max_subagents_per_run]
        add_event(self.db, run.id, "subtasks_created", "Created subagent assignments", f"Created {len(subtasks)} focused research subtasks.")
        persisted: list[dict[str, Any]] = []
        for index, subtask in enumerate(subtasks, start=1):
            row = ResearchSubtask(
                run_id=run.id,
                title=subtask["title"],
                instructions=subtask.get("objective") or subtask.get("instructions") or subtask["title"],
                status="pending",
                sequence_number=index,
            )
            self.db.add(row)
            self.db.flush()
            persisted.append({**subtask, "id": str(row.id), "sequence_number": index})
        self.db.commit()
        return {**state, "subtasks": persisted}

    def run_subagents(self, state: AgentState) -> AgentState:
        run = self._run(state)
        all_findings: list[dict[str, Any]] = []
        all_sources: list[dict[str, Any]] = []
        for subtask in state["subtasks"]:
            subtask_id = UUID(subtask["id"])
            subtask_row = self.db.get(ResearchSubtask, subtask_id)
            if subtask_row is None:
                continue
            subtask_row.status = "running"
            subtask_row.started_at = datetime.now(timezone.utc)
            self.db.commit()
            add_event(self.db, run.id, "subagent_started", f"Researching {subtask['title']}", subtask_row.instructions)

            query_results: list[dict[str, Any]] = []
            for query in subtask.get("search_queries") or [state["user_prompt"]]:
                add_event(self.db, run.id, "search_query", "Searching web", query)
                results = search_web(query, self.settings)
                query_results.extend(results)
                for result in results:
                    url = result.get("url")
                    add_event(
                        self.db,
                        run.id,
                        "url_found",
                        "Found source",
                        result.get("title") or url or "Untitled source",
                        url=url,
                        metadata={"score": result.get("score"), "subtask_id": str(subtask_id)},
                    )

            unique_results = {result.get("url"): result for result in query_results if result.get("url")}
            extracted = extract_sources(list(unique_results.keys())[: self.settings.max_search_results_per_subtask], self.settings)
            extracted_by_url = {item.get("url"): item for item in extracted if item.get("url")}
            stored_sources: list[dict[str, Any]] = []
            for result in unique_results.values():
                url = result["url"]
                extracted_item = extracted_by_url.get(url, {})
                source = ResearchSource(
                    run_id=run.id,
                    subtask_id=subtask_id,
                    url=url,
                    title=result.get("title"),
                    domain=domain_from_url(url),
                    summary=result.get("content"),
                    extracted_text=extracted_item.get("raw_content") or extracted_item.get("content"),
                    relevance=str(result.get("score")) if result.get("score") is not None else None,
                )
                self.db.add(source)
                self.db.flush()
                stored = {
                    "id": str(source.id),
                    "url": source.url,
                    "title": source.title,
                    "content": source.extracted_text or source.summary,
                }
                stored_sources.append(stored)
                all_sources.append(stored)
                add_event(self.db, run.id, "source_read", "Read source", source.title or source.url, url=source.url)

            result = research_subtask(state["user_prompt"], subtask, stored_sources or list(unique_results.values()), self.settings)
            for finding in result.findings:
                row = ResearchFinding(
                    run_id=run.id,
                    subtask_id=subtask_id,
                    claim=finding.claim,
                    evidence=finding.evidence,
                    source_urls=finding.source_urls,
                    confidence=finding.confidence,
                    gaps=finding.gaps,
                )
                self.db.add(row)
                self.db.flush()
                finding_dict = finding.model_dump()
                finding_dict["id"] = str(row.id)
                finding_dict["subtask_title"] = subtask["title"]
                all_findings.append(finding_dict)
                add_event(self.db, run.id, "finding_extracted", "Extracted finding", finding.claim, metadata={"confidence": finding.confidence})

            subtask_row.status = "completed"
            subtask_row.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            add_event(self.db, run.id, "subagent_completed", f"Completed {subtask['title']}", result.summary)
        return {**state, "findings": all_findings, "sources": all_sources}

    def synthesize(self, state: AgentState) -> AgentState:
        run = self._run(state)
        add_event(self.db, run.id, "synthesis_started", "Synthesizing report", "The main agent is combining subagent findings.")
        report = synthesize_report(state["user_prompt"], state["approved_plan"], state["findings"], self.settings)
        add_event(self.db, run.id, "synthesis_completed", "Synthesized report", "A draft report was generated from the collected findings.")
        return {**state, "final_report": report}

    def critique(self, state: AgentState) -> AgentState:
        run = self._run(state)
        result = critique_report(state["user_prompt"], state["approved_plan"], state["final_report"], state["findings"], self.settings)
        content = "Report passed critique." if result.passed else "; ".join(result.issues)
        add_event(self.db, run.id, "critique_completed", "Critiqued report", content, metadata=result.model_dump())
        return {**state, "critique": result.model_dump()}

    def save_report(self, state: AgentState) -> AgentState:
        run = self._run(state)
        now = datetime.now(timezone.utc)
        report_message = Message(
            conversation_id=run.conversation_id,
            role=MessageRole.assistant.value,
            content=state["final_report"],
            research_run_id=run.id,
        )
        self.db.add(report_message)
        self.db.flush()
        self.db.add(ResearchReport(run_id=run.id, message_id=report_message.id, markdown=state["final_report"]))
        run.status = RunStatus.completed.value
        run.completed_at = now
        if run.started_at:
            run.duration_seconds = max(1, int((now - run.started_at).total_seconds()))
        self.db.commit()
        add_event(self.db, run.id, "run_completed", "Research completed", "The final report was saved.")
        return state
