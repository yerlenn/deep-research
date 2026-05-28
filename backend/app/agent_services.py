import json
import re
from typing import Any
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from tavily import TavilyClient

from .agent_types import CritiqueResult, FindingModel, ResearchPlanModel, SubtaskResult
from .config import Settings
from .mock_agent import build_plan, build_report


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan["steps"] = [re.sub(r"^\s*\d+[\.)]\s*", "", str(step)).strip() for step in plan.get("steps", [])]
    return plan


def _llm(settings: Settings, temperature: float = 0.2) -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=temperature)


def make_plan(prompt: str, feedback: str | None, settings: Settings) -> dict[str, Any]:
    if not settings.openai_api_key:
        fallback = build_plan(prompt, feedback)
        fallback["scope"] = "General web research"
        fallback["subtopics"] = [
            {"title": "Context", "objective": f"Establish background for {prompt}", "search_queries": [prompt]},
            {"title": "Evidence", "objective": f"Find credible evidence for {prompt}", "search_queries": [f"{prompt} data sources"]},
            {"title": "Risks", "objective": f"Identify uncertainty and caveats for {prompt}", "search_queries": [f"{prompt} risks caveats"]},
        ]
        fallback["risks"] = ["This fallback plan was created without an LLM because OPENAI_API_KEY is not configured."]
        return normalize_plan(fallback)

    model = _llm(settings).with_structured_output(ResearchPlanModel)
    response = model.invoke(
        [
            (
                "system",
                "You are a careful research planner. Create a specific plan that can be executed by multiple web research subagents.",
            ),
            (
                "human",
                json.dumps({"prompt": prompt, "feedback": feedback}, ensure_ascii=False),
            ),
        ]
    )
    return normalize_plan(response.model_dump())


def search_web(query: str, settings: Settings) -> list[dict[str, Any]]:
    if not settings.tavily_api_key:
        return [
            {
                "title": f"Mock source for {query}",
                "url": "https://example.com/mock-source",
                "content": f"Mock search result for {query}. Configure TAVILY_API_KEY for real search.",
                "score": 0.5,
            }
        ]

    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=settings.max_search_results_per_subtask,
        include_answer=False,
        include_raw_content=False,
    )
    return response.get("results", [])


def extract_sources(urls: list[str], settings: Settings) -> list[dict[str, Any]]:
    if not settings.tavily_api_key or not urls:
        return []
    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.extract(urls=urls)
    return response.get("results", [])


def domain_from_url(url: str) -> str | None:
    try:
        return urlparse(url).netloc
    except ValueError:
        return None


def source_label(url: str) -> str:
    domain = domain_from_url(url)
    return domain.replace("www.", "") if domain else "source"


def unique_source_urls(findings: list[dict[str, Any]], limit: int = 8) -> list[str]:
    urls: list[str] = []
    for finding in findings:
        for url in finding.get("source_urls") or []:
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
    return urls


def ensure_report_has_sources(report: str, findings: list[dict[str, Any]]) -> str:
    if re.search(r"\[[^\]]+\]\(https?://", report) or re.search(r"https?://", report):
        return report
    urls = unique_source_urls(findings)
    if not urls:
        return report
    source_lines = [f"- [{source_label(url)}]({url})" for url in urls]
    return f"{report.rstrip()}\n\n## Sources consulted\n" + "\n".join(source_lines)


def research_subtask(prompt: str, subtask: dict[str, Any], search_results: list[dict[str, Any]], settings: Settings) -> SubtaskResult:
    source_summaries = [
        {
            "title": result.get("title"),
            "url": result.get("url"),
            "content": result.get("content") or result.get("raw_content") or result.get("summary"),
        }
        for result in search_results
    ]
    if not settings.openai_api_key:
        urls = [item["url"] for item in source_summaries if item.get("url")]
        return SubtaskResult(
            title=subtask["title"],
            summary=f"Mock findings for {subtask['title']}.",
            findings=[
                FindingModel(
                    claim=f"{subtask['title']} needs real verification.",
                    evidence="Configure OPENAI_API_KEY and TAVILY_API_KEY to replace this fallback finding.",
                    source_urls=urls,
                    confidence="low",
                    gaps="Real model analysis was not run.",
                )
            ],
            gaps=["Missing real LLM/search configuration."],
        )

    model = _llm(settings).with_structured_output(SubtaskResult)
    response = model.invoke(
        [
            (
                "system",
                "You are a research subagent. Use only the provided search/source material. Return concise findings. "
                "Every factual finding must include source_urls from the provided sources when a source supports it. "
                "If no source supports a claim, mark confidence low and explain the gap instead of inventing evidence.",
            ),
            (
                "human",
                json.dumps(
                    {
                        "prompt": prompt,
                        "subtask": subtask,
                        "sources": source_summaries,
                        "citation_rule": "Attach the relevant source URL(s) to each finding.source_urls. Prefer 1-3 strongest URLs.",
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
    )
    return response


def synthesize_report(prompt: str, plan: dict[str, Any], findings: list[dict[str, Any]], settings: Settings) -> str:
    if not settings.openai_api_key:
        return build_report(prompt)

    model = _llm(settings, temperature=0.1)
    response = model.invoke(
        [
            (
                "system",
                "You write careful deep research reports. Use the supplied findings only, state uncertainty, and avoid unsupported claims. "
                "Use valid GitHub-flavored Markdown. For tables, put each row on its own line with a proper separator row. "
                "Do not paste raw URLs inline. Cite sources with Markdown links using short source names. "
                "Cite important factual claims, rankings, dates, numbers, funding amounts, quotes, and comparative table rows when source URLs are available. "
                "Do not cite every sentence; cite where a reader would naturally want to verify the claim. "
                "Do not end with offers, follow-up suggestions, or phrases like 'If you want', 'I can', or 'Would you like'.",
            ),
            (
                "human",
                json.dumps(
                    {
                        "prompt": prompt,
                        "plan": plan,
                        "findings": findings,
                        "citation_rule": "Use the source_urls attached to findings. Add citations near the claim or in the relevant table cell.",
                    },
                    ensure_ascii=False,
                ),
            ),
        ]
    )
    return ensure_report_has_sources(str(response.content), findings)


def critique_report(prompt: str, plan: dict[str, Any], report: str, findings: list[dict[str, Any]], settings: Settings) -> CritiqueResult:
    if not settings.openai_api_key:
        return CritiqueResult(passed=True)

    model = _llm(settings, temperature=0.0).with_structured_output(CritiqueResult)
    response = model.invoke(
        [
            (
                "system",
                "You are a strict research QA reviewer. Check if the report answers the prompt using only the supplied findings. "
                "Also check that important factual claims have Markdown citations when the supplied findings include source URLs.",
            ),
            (
                "human",
                json.dumps({"prompt": prompt, "plan": plan, "report": report, "findings": findings}, ensure_ascii=False),
            ),
        ]
    )
    return response
