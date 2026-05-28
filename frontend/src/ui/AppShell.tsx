import { ArrowUp, BookOpen, Check, ChevronRight, Edit3, ExternalLink, FileText, PanelLeft, Search, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";

import { approveResearchRun, createFollowup, createResearchRun, getConversation, getResearchEvents, listConversations, sendPlanFeedback } from "../api";
import { useAppAuth } from "../auth";
import type { Conversation, ConversationSummary, ResearchEvent, ResearchRunSummary } from "../types";

const pendingPromptKey = "pendingResearchPrompt";

type ReplyTarget = {
  runId: string;
  title: string;
  excerpt: string;
};

type PlanningState = {
  prompt: string;
  mode: "create" | "update";
  runId?: string;
};

function formatDuration(seconds: number | null) {
  if (!seconds) return "a moment";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

function formatReportMarkdown(markdown: string) {
  return markdown.replace(/(?<!\]\()https?:\/\/[^\s)\]]+/g, (url) => {
    let label = "Source";
    try {
      label = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      label = "Source";
    }
    return `[${label}](${url})`;
  });
}

function stripLeadingNumber(value: string) {
  return value.replace(/^(\s*\d+[\.)]\s*)+/, "");
}

export function AppShell() {
  const { isLoaded, isSignedIn, getToken, userControl } = useAppAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  async function refreshConversations() {
    if (!isLoaded || !isSignedIn) return;
    setConversations(await listConversations(getToken));
  }

  useEffect(() => {
    void refreshConversations();
  }, [isLoaded, isSignedIn]);

  return (
    <div className="app">
      <aside className={sidebarOpen ? "sidebar open" : "sidebar"}>
        <div className="sidebar-panel">
          <div className="sidebar-brand">
            <span className="brand-mark" aria-hidden="true" />
            <span>Deep Research</span>
          </div>
          <div className="sidebar-top">
            <Link className="new-chat" to="/">
              <Edit3 size={16} />
              New research
            </Link>
            <button className="icon-button mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar">
              <X size={18} />
            </button>
          </div>
          <nav className="conversation-list">
            {conversations.map((item) => (
              <NavLink
                key={item.id}
                to={`/c/${item.id}`}
                className={({ isActive }) => (isActive ? "conversation-link active" : "conversation-link")}
              >
                <span>{item.title}</span>
                <ChevronRight size={14} />
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="icon-button" onClick={() => setSidebarOpen((value) => !value)} aria-label="Toggle sidebar">
            <PanelLeft size={18} />
          </button>
          <div />
          <div className="user-slot">{userControl}</div>
        </header>
        <Routes>
          <Route path="/" element={<NewChat onCreated={refreshConversations} />} />
          <Route path="/c/:conversationId" element={<ConversationPage onChanged={refreshConversations} />} />
        </Routes>
      </main>
    </div>
  );
}

function NewChat({ onCreated }: { onCreated: () => Promise<void> }) {
  const auth = useAppAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [planningState, setPlanningState] = useState<PlanningState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(pendingPromptKey);
    if (saved) {
      setPrompt(saved);
    }
  }, []);

  async function submit() {
    const clean = prompt.trim();
    if (!clean) return;
    if (!auth.isSignedIn) {
      sessionStorage.setItem(pendingPromptKey, clean);
      setAuthModalOpen(true);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    setPrompt("");
    setPlanningState({ prompt: clean, mode: "create" });
    try {
      const response = await createResearchRun(clean, auth.getToken);
      sessionStorage.removeItem(pendingPromptKey);
      await onCreated();
      navigate(`/c/${response.conversation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create research run");
    } finally {
      setIsSubmitting(false);
      setPlanningState(null);
    }
  }

  if (planningState) {
    return (
      <section className="conversation-screen">
        <div className="message-stack">
          <article className="message user-message">
            <div className="message-content">{planningState.prompt}</div>
          </article>
          <PlanningMessage state={planningState} />
        </div>
        <div className="composer-dock">
          <Composer
            value={prompt}
            onChange={setPrompt}
            onSubmit={submit}
            disabled={isSubmitting}
            placeholder="Ask a research question..."
          />
        </div>
      </section>
    );
  }

  return (
    <section className="new-chat-screen">
      <div className="new-chat-copy">
        <h1>What should we research?</h1>
      </div>
      <Composer value={prompt} onChange={setPrompt} onSubmit={submit} disabled={isSubmitting} placeholder="Ask a research question..." />
      {error && <p className="error-text">{error}</p>}
      {authModalOpen && <AuthRequiredModal onClose={() => setAuthModalOpen(false)} />}
    </section>
  );
}

function ConversationPage({ onChanged }: { onChanged: () => Promise<void> }) {
  const { conversationId } = useParams();
  const auth = useAppAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [prompt, setPrompt] = useState("");
  const [planningState, setPlanningState] = useState<PlanningState | null>(null);
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!conversationId) return;
    setConversation(await getConversation(conversationId, auth.getToken));
  }

  useEffect(() => {
    setLoading(true);
    setError(null);
    refresh()
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load conversation"))
      .finally(() => setLoading(false));
  }, [conversationId]);

  useEffect(() => {
    if (!conversation) return;
    const hasActiveRun = conversation.pending_runs.some((run) => run.status === "queued" || run.status === "running");
    if (!hasActiveRun) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [conversation, conversationId]);

  async function submitFollowup() {
    if (!conversationId || !prompt.trim()) return;
    const content = prompt.trim();
    const activeReply = replyTarget;
    setPrompt("");
    setReplyTarget(null);
    setIsSubmitting(true);
    setPlanningState({ prompt: content, mode: activeReply ? "update" : "create", runId: activeReply?.runId });
    try {
      if (activeReply) {
        await sendPlanFeedback(activeReply.runId, content, auth.getToken);
      } else {
        await createFollowup(conversationId, content, auth.getToken);
      }
      await refresh();
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message");
    } finally {
      setPlanningState(null);
      setIsSubmitting(false);
    }
  }

  async function handleRunChanged() {
    await refresh();
    await onChanged();
  }

  if (loading) return <div className="center-state">Loading conversation...</div>;
  if (error) return <div className="center-state error-text">{error}</div>;
  if (!conversation) return <div className="center-state">Conversation not found.</div>;

  return (
    <section className="conversation-screen">
      <div className="message-stack">
        {conversation.messages.map((message) => (
          <MessageBlock key={message.id} message={message} onRunChanged={handleRunChanged} onEditPlan={setReplyTarget} />
        ))}
        {conversation.pending_runs.map((run) => (
          <PendingRunBlock
            key={run.id}
            run={run}
            onChanged={handleRunChanged}
            onEditPlan={setReplyTarget}
            updatingState={planningState?.mode === "update" && planningState.runId === run.id ? planningState : null}
          />
        ))}
        {planningState?.mode === "create" && <PlanningMessage state={planningState} />}
      </div>
      <div className="composer-dock">
        <Composer
          value={prompt}
          onChange={setPrompt}
          onSubmit={submitFollowup}
          placeholder={replyTarget ? "Tell the agent what to change..." : "Ask a follow-up..."}
          disabled={isSubmitting}
          replyTarget={replyTarget}
          onCancelReply={() => setReplyTarget(null)}
          autoFocusKey={replyTarget?.runId}
        />
      </div>
    </section>
  );
}

function PendingRunBlock({
  run,
  onChanged,
  onEditPlan,
  updatingState
}: {
  run: ResearchRunSummary;
  onChanged: () => Promise<void>;
  onEditPlan: (target: ReplyTarget) => void;
  updatingState?: PlanningState | null;
}) {
  const history = run.plan_history ?? [];
  const hasHistory = history.length > 0;

  if (updatingState) {
    return (
      <>
        {history.map((item, index) => (
          <PlanHistoryBlock key={`${run.id}-history-${index}`} item={item} run={run} />
        ))}
        {run.plan && <PlanCard run={run} onChanged={onChanged} onEditPlan={onEditPlan} readonly />}
        <article className="message user-message">
          <div className="message-content">{updatingState.prompt}</div>
        </article>
        <PlanningMessage state={updatingState} />
      </>
    );
  }

  const renderedHistory = history.map((item, index) => (
    <PlanHistoryBlock key={`${run.id}-history-${index}`} item={item} run={run} />
  ));

  if (run.status === "planning") {
    return (
      <>
        {renderedHistory}
        <PlanningMessage
          state={{
            prompt: run.plan?.goal ?? "Preparing your research plan",
            mode: hasHistory ? "update" : "create",
            runId: run.id
          }}
        />
      </>
    );
  }
  if (run.status === "awaiting_approval") {
    return (
      <>
        {renderedHistory}
        <PlanCard run={run} onChanged={onChanged} onEditPlan={onEditPlan} />
      </>
    );
  }
  return (
    <>
      {renderedHistory}
      <article className="message assistant-message">
        <RunSummary run={run} />
      </article>
    </>
  );
}

function PlanHistoryBlock({
  item,
  run
}: {
  item: NonNullable<ResearchRunSummary["plan_history"]>[number];
  run: ResearchRunSummary;
}) {
  return (
    <>
      <PlanCard run={{ ...run, plan: item.plan, status: "awaiting_approval" }} readonly />
      {item.feedback && (
        <article className="message user-message">
          <div className="message-content">{item.feedback}</div>
        </article>
      )}
    </>
  );
}

function PlanningMessage({ state }: { state: PlanningState }) {
  const title = state.mode === "update" ? "Updating research plan" : "Making a research plan";
  return (
    <article className="message assistant-message planning-message" role="status">
      <span className="thinking-dot" />
      <div>
        <strong>{title}</strong>
        <p>{state.prompt}</p>
      </div>
    </article>
  );
}

function MessageBlock({
  message,
  onRunChanged,
  onEditPlan
}: {
  message: Conversation["messages"][number];
  onRunChanged: () => Promise<void>;
  onEditPlan: (target: ReplyTarget) => void;
}) {
  const isUser = message.role === "user";
  return (
    <article className={isUser ? "message user-message" : "message assistant-message"}>
      {message.research_run && <RunSummary run={message.research_run} />}
      {isUser ? (
        <div className="message-content">{message.content}</div>
      ) : (
        <div className="message-content markdown-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => (
                <a className="markdown-source-chip" href={href} target="_blank" rel="noreferrer">
                  {children}
                  <ExternalLink size={12} />
                </a>
              ),
              table: ({ children }) => (
                <div className="markdown-table-scroll">
                  <table>{children}</table>
                </div>
              )
            }}
          >
            {formatReportMarkdown(message.content)}
          </ReactMarkdown>
        </div>
      )}
      {!isUser && message.research_run?.status === "awaiting_approval" && (
        <PlanCard run={message.research_run} onChanged={onRunChanged} onEditPlan={onEditPlan} />
      )}
    </article>
  );
}

function PlanCard({
  run,
  onChanged,
  onEditPlan,
  readonly = false
}: {
  run: ResearchRunSummary;
  onChanged?: () => Promise<void>;
  onEditPlan?: (target: ReplyTarget) => void;
  readonly?: boolean;
}) {
  const auth = useAppAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const plan = run.plan;

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      await approveResearchRun(run.id, auth.getToken);
      await onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve plan");
    } finally {
      setBusy(false);
    }
  }

  if (!plan || run.status !== "awaiting_approval") return null;

  return (
    <section className="plan-card">
      <div className="section-eyebrow">Agent plan</div>
      <h2>{plan.title}</h2>
      <p>{plan.goal}</p>
      <ol>
        {plan.steps.map((step, index) => (
          <li key={`${step}-${index}`}>{stripLeadingNumber(step)}</li>
        ))}
      </ol>
      <p className="muted">{plan.expected_output}</p>
      {!readonly && (
        <div className="plan-actions">
          <button className="button primary" onClick={approve} disabled={busy}>
            <Check size={16} />
            Approve
          </button>
          <button
            className="button"
            onClick={() =>
              onEditPlan?.({
                runId: run.id,
                title: "Research plan",
                excerpt: `${plan.title}: ${plan.goal}`
              })
            }
            disabled={busy}
          >
            <Edit3 size={16} />
            Edit
          </button>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}

function RunSummary({ run }: { run: ResearchRunSummary }) {
  const auth = useAppAuth();
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const label = useMemo(() => {
    if (run.status === "completed") return `Agent researched for ${formatDuration(run.duration_seconds)}`;
    if (run.status === "queued") return "Research queued...";
    if (run.status === "running") return "Agent is researching...";
    if (run.status === "failed") return "Research failed";
    return "Agent is preparing research...";
  }, [run]);

  async function openEvents() {
    setOpen(true);
    setLoading(true);
    try {
      setEvents(await getResearchEvents(run.id, auth.getToken));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    const timer = window.setInterval(() => {
      getResearchEvents(run.id, auth.getToken)
        .then(setEvents)
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [open, run.id]);

  return (
    <>
      <button className="run-summary" onClick={openEvents}>
        <Search size={16} />
        <span>{label}</span>
      </button>
      {open && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="process-modal">
            <div className="modal-header">
              <div>
                <div className="section-eyebrow">Agent process</div>
                <h2>Research history</h2>
              </div>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="Close process log">
                <X size={18} />
              </button>
            </div>
            {loading ? (
              <p className="muted">Loading process...</p>
            ) : (
              <div className="event-list">
                {events.map((event) => (
                  <div className="event-row" key={event.id}>
                    <div className="event-icon">
                      <BookOpen size={15} />
                    </div>
                    <div>
                      <h3>{event.title}</h3>
                      <p>{event.content}</p>
                      {event.url && <SourceChip url={event.url} />}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function SourceChip({ url }: { url: string }) {
  let label = "Source";
  try {
    label = new URL(url).hostname.replace(/^www\./, "");
  } catch {
    label = "Open source";
  }
  return (
    <a className="source-chip" href={url} target="_blank" rel="noreferrer">
      <ExternalLink size={13} />
      {label}
    </a>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  replyTarget,
  onCancelReply,
  autoFocusKey
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  disabled?: boolean;
  placeholder: string;
  replyTarget?: ReplyTarget | null;
  onCancelReply?: () => void;
  autoFocusKey?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (autoFocusKey) {
      textareaRef.current?.focus();
    }
  }, [autoFocusKey]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void onSubmit();
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      {replyTarget && (
        <div className="reply-preview">
          <div className="reply-icon">↳</div>
          <div>
            <strong>Replying to {replyTarget.title}</strong>
            <p>{replyTarget.excerpt}</p>
          </div>
          <button type="button" className="reply-close" onClick={onCancelReply} aria-label="Cancel reply">
            <X size={16} />
          </button>
        </div>
      )}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void onSubmit();
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button className="send-button" disabled={disabled || !value.trim()} aria-label="Send research request">
        <ArrowUp size={18} />
      </button>
    </form>
  );
}

function AuthRequiredModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="auth-required-modal">
        <button className="icon-button close-modal" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        <FileText size={22} />
        <h2>Sign in to start research</h2>
        <p>Your prompt is saved. After signing in, it will be restored here for you to review and send.</p>
        <div className="modal-actions">
          <Link className="button primary" to="/sign-in">
            Sign in
          </Link>
          <Link className="button" to="/sign-up">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
}
