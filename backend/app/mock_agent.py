from datetime import datetime, timezone


def title_from_prompt(prompt: str) -> str:
    clean = " ".join(prompt.strip().split())
    if not clean:
        return "New research"
    return clean[:60] + ("..." if len(clean) > 60 else "")


def build_plan(prompt: str, feedback: str | None = None) -> dict:
    base_steps = [
        "Clarify the research question and define the decision the report should support.",
        "Search for recent credible sources, including primary documents where available.",
        "Read and extract claims, numbers, dates, and source context.",
        "Compare sources for agreement, disagreement, recency, and credibility.",
        "Synthesize findings into a concise report with caveats and next questions.",
    ]
    if feedback:
        base_steps.insert(1, f"Adjust the scope based on user feedback: {feedback}")

    return {
        "title": title_from_prompt(prompt),
        "goal": f"Research: {prompt}",
        "steps": base_steps,
        "expected_output": "A structured research report with key findings, evidence, caveats, and suggested follow-ups.",
        "revision_note": feedback,
    }


def build_research_intro(prompt: str) -> str:
    return (
        "I'm researching this by checking recent web sources, primary references when possible, "
        "source consistency, and the strongest evidence for the final report."
    )


def build_events(prompt: str) -> list[dict]:
    search_query = prompt.strip().replace('"', "")
    sources = [
        ("Searching web", f'"{search_query}" latest analysis', None),
        ("Opened URL", "Reviewing a market overview page for high-level context.", "https://example.com/market-overview"),
        ("Reading source", "Reading the overview and identifying claims that need stronger support.", None),
        ("Extracted note", "Noted market size, growth drivers, and important caveats to verify elsewhere.", None),
        ("Searching web", f'"{search_query}" company filings primary source', None),
        ("Opened URL", "Checking a company filing or investor document.", "https://example.com/company-filing"),
        ("Reading section", "Reading the sections most relevant to capacity, strategy, and recent changes.", None),
        ("Extracted note", "Captured concrete numbers and dates for later comparison.", None),
        ("Searching web", f'"{search_query}" recent news risks competition', None),
        ("Opened URL", "Checking recent reporting for developments after older reports.", "https://example.com/recent-news"),
        ("Compared sources", "Compared the report, filing, and news claims for consistency.", None),
        ("Skipped source", "Skipped a low-detail summary because it did not cite primary evidence.", "https://example.com/low-quality-summary"),
        ("Updated plan", "Added an extra pass to check whether recent news changes the initial thesis.", None),
        ("Synthesized evidence", "Grouped findings into market context, major players, risks, and open questions.", None),
        ("Completed research", "Prepared the final report from the strongest available evidence.", None),
    ]
    return [
        {
            "sequence_number": index + 1,
            "event_type": title.lower().replace(" ", "_"),
            "title": title,
            "content": content,
            "url": url,
            "metadata": {"mocked": True},
        }
        for index, (title, content, url) in enumerate(sources)
    ]


def build_report(prompt: str) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""# Research Report

## Question
{prompt}

## Key Findings
- The strongest answer depends on recent, source-backed evidence rather than a single summary.
- Primary materials and recent reporting should be compared before treating any claim as settled.
- The mocked research flow found likely drivers, risks, and open questions that a real agent would verify deeply.

## Evidence Approach
The agent checked market context, source quality, recent changes, and contradictions before writing this report.

## Caveats
This is a mocked report generated for the starter app on {generated_at}. Real web research and citation extraction will be added later.
"""
