# Deep Research

Deep Research is a research-agent web app for turning broad questions into structured, source-backed reports.

Instead of answering immediately, the system first creates a research plan, asks the user to approve or revise it, runs multiple focused research agents, and then synthesizes the collected findings into a final report.

## Why This Exists

Deep research workflows are becoming a core interaction pattern in AI products. ChatGPT Deep Research and Gemini Deep Research show how useful it is when an assistant can spend more time searching, reading, comparing sources, and producing a structured answer instead of giving a quick chat response.

This project explores that pattern as an independent product experience:

- The user starts with a natural-language research question.
- The app turns that question into a reviewable plan.
- The user stays in control before research begins.
- Multiple research agents investigate focused parts of the plan.
- The final answer is synthesized into a readable report with research process visibility.

## What It Does

- Provides a chat-style research interface.
- Creates a research plan before starting.
- Lets the user approve the plan or ask for changes.
- Runs focused research agents after approval.
- Shows a live research status inside the conversation.
- Exposes the ordered research process so the user can inspect what happened.
- Produces a final synthesized report.
- Keeps conversations and research runs organized for later review.

## High-Level Architecture

```text
User question
    |
    v
Planning agent
    |
    v
User reviews plan
    |
    |-- Edit request --> Planning agent revises plan
    |
    v
User approves plan
    |
    v
Research orchestration
    |
    v
Multiple focused research agents
    |
    v
Findings, sources, caveats, conflicts
    |
    v
Synthesis agent
    |
    v
Final research report
```

At a high level, the app separates the research workflow into four stages:

1. **Plan**
   The planner turns the user question into a concrete research plan.

2. **Approve**
   The user reviews the plan before any deeper research starts.

3. **Research**
   Focused agents investigate parts of the approved plan and collect findings.

4. **Synthesize**
   The system combines the research into a final report with source-aware reasoning and caveats.

## How To Use

1. Open the app.
2. Ask a research question in the chat composer.
3. Review the generated research plan.
4. Click **Approve** to begin research, or click **Edit** and tell the agent what to change.
5. While research runs, click the research status row to inspect the process log.
6. Read the final report when the research completes.
7. Continue in the same conversation with follow-up research prompts.

## Example Research Requests

- “Research consumer AI adoption rates by country and make a ranking.”
- “Research Anthropic’s history, founders, funding, business model, and IPO plans.”

## Product Principles

- **Plan before action:** the user should understand the research direction before the system spends time and tokens.
- **Visible process:** research should not feel like a black box.
- **Source awareness:** claims should be grounded in sources when available.
- **Editable direction:** the user should be able to steer the plan without manually editing internal agent instructions.
- **Conversation continuity:** a chat can contain multiple research runs, not just one isolated report.
