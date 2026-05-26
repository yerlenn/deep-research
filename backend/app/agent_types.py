from typing import Any, TypedDict

from pydantic import BaseModel, Field


class PlanSubtopic(BaseModel):
    title: str = Field(description="Focused subtopic title")
    objective: str = Field(description="What this subagent should learn")
    search_queries: list[str] = Field(description="Search queries to try first")


class ResearchPlanModel(BaseModel):
    title: str
    goal: str
    scope: str
    subtopics: list[PlanSubtopic]
    steps: list[str]
    expected_output: str
    risks: list[str] = Field(default_factory=list)


class FindingModel(BaseModel):
    claim: str
    evidence: str
    source_urls: list[str]
    confidence: str = "medium"
    gaps: str | None = None


class SubtaskResult(BaseModel):
    title: str
    summary: str
    findings: list[FindingModel]
    gaps: list[str] = Field(default_factory=list)


class CritiqueResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    recommended_action: str = "pass"
    revision_instruction: str | None = None


class AgentState(TypedDict, total=False):
    run_id: str
    conversation_id: str
    user_prompt: str
    approved_plan: dict[str, Any]
    subtasks: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    final_report: str
    critique: dict[str, Any]
    errors: list[str]
